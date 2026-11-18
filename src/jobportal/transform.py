"""Transform: clean, standardise and enrich raw postings."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import (ANNUAL_SALARY_RANGE, EXPERIENCE_LEVELS, JOB_FAMILIES,
                     PAY_PERIOD_TO_ANNUAL, POSTING_COLUMNS, SKILLS, US_STATES)


def _non_capturing(pattern: str) -> str:
    """Turn '(' groups into '(?:' so pandas doesn't warn about unused capture groups."""
    return re.sub(r"(?<!\\)\((?!\?)", "(?:", pattern)


STATE_BY_NAME = {v.lower(): k for k, v in US_STATES.items()}
CASE_SENSITIVE_SKILLS = {"R"}
SKILL_PATTERNS = {
    name: re.compile(_non_capturing(p), 0 if name in CASE_SENSITIVE_SKILLS else re.IGNORECASE)
    for name, p in SKILLS.items()
}

TITLE_EXPERIENCE_RULES = [
    (r"\bintern(ship)?\b", "Internship"),
    (r"\b(director|head of|vp|vice president)\b", "Director"),
    (r"\b(chief|cxo|ceo|cfo|cto)\b", "Executive"),
    (r"\b(senior|sr\.?|lead|principal|staff|manager)\b", "Mid-Senior level"),
    (r"\b(junior|jr\.?|entry|graduate|trainee)\b", "Entry level"),
    (r"\b(associate)\b", "Associate"),
]
WORK_TYPE_RULES = [
    (r"part[\s-]?time", "Part-time"), (r"\bcontract(or)?\b", "Contract"),
    (r"\btemp(orary)?\b", "Temporary"), (r"\binternship\b|\bintern\b", "Internship"),
    (r"full[\s-]?time", "Full-time"),
]


# ---------------------------------------------------------------- cleaning helpers
def clean_title(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    s = s.str.replace(r"\s*[\(\[].*?(remote|hybrid|onsite|on-site|urgent|hiring).*?[\)\]]",
                      "", regex=True, flags=re.IGNORECASE)
    s = s.str.replace(r"\s*[-|]\s*(remote|hybrid|urgent.*)$", "", regex=True, flags=re.IGNORECASE)
    s = s.str.strip(" -|,")
    return s.where(s.str.len() > 2)


def job_family(title: pd.Series) -> pd.Series:
    t = " " + title.fillna("").str.lower() + " "
    out = pd.Series("Other", index=title.index, dtype="object")
    assigned = pd.Series(False, index=title.index)
    for family, keywords in JOB_FAMILIES:
        hit = t.str.contains("|".join(map(re.escape, keywords)), regex=True) & ~assigned
        out[hit] = family
        assigned |= hit
    return out


def parse_location(loc: pd.Series) -> pd.DataFrame:
    loc = loc.astype("string").str.strip()
    parts = loc.str.split(",")
    last = parts.str[-1].str.strip()
    first = parts.str[0].str.strip()
    code = last.where(last.isin(US_STATES.keys()))
    by_name = last.str.lower().map(STATE_BY_NAME)
    first_by_name = first.str.lower().map(STATE_BY_NAME)  # e.g. "California" alone
    code = code.fillna(by_name).fillna(first_by_name)
    city = first.where(parts.str.len() > 1)
    is_remote_loc = loc.str.contains("remote", case=False, na=False)
    return pd.DataFrame({
        "city": city.where(~is_remote_loc),
        "state_code": code,
        "state_name": code.map(US_STATES),
        "country": np.where(code.notna() | loc.str.contains("United States", na=False),
                            "United States", "Other/Unknown"),
    }, index=loc.index)


def annual_salary(df: pd.DataFrame) -> pd.DataFrame:
    mult = df["pay_period"].astype("string").str.upper().str.strip().map(PAY_PERIOD_TO_ANNUAL)
    out = pd.DataFrame(index=df.index)
    for col in ("min_salary", "med_salary", "max_salary"):
        out[col.replace("salary", "annual")] = pd.to_numeric(df[col], errors="coerce") * mult
    # fix swapped min/max
    swap = out["min_annual"] > out["max_annual"]
    out.loc[swap, ["min_annual", "max_annual"]] = out.loc[swap, ["max_annual", "min_annual"]].values
    out["salary_annual"] = out["med_annual"].fillna(out[["min_annual", "max_annual"]].mean(axis=1))
    lo, hi = ANNUAL_SALARY_RANGE
    invalid = ~out["salary_annual"].between(lo, hi)
    out.loc[invalid, ["min_annual", "med_annual", "max_annual", "salary_annual"]] = np.nan
    # only USD salaries are comparable
    if "currency" in df:
        non_usd = df["currency"].notna() & (df["currency"].astype("string").str.upper() != "USD")
        out.loc[non_usd, :] = np.nan
    out["salary_disclosed"] = out["salary_annual"].notna()
    out["salary_band"] = pd.cut(out["salary_annual"],
                                [0, 50e3, 75e3, 100e3, 150e3, 200e3, np.inf],
                                labels=["<50K", "50-75K", "75-100K", "100-150K", "150-200K", "200K+"])
    return out


def _infer(text: pd.Series, rules) -> pd.Series:
    out = pd.Series(pd.NA, index=text.index, dtype="object")
    for pattern, label in rules:
        hit = text.str.contains(_non_capturing(pattern), case=False, regex=True, na=False) & out.isna()
        out[hit] = label
    return out


def experience_level(df: pd.DataFrame) -> pd.Series:
    given = df["formatted_experience_level"].astype("string").str.strip().str.lower().map(EXPERIENCE_LEVELS)
    inferred = _infer(df["title"].astype("string"), TITLE_EXPERIENCE_RULES)
    return given.fillna(inferred).fillna("Not specified")


def work_type(df: pd.DataFrame) -> pd.Series:
    given = df["formatted_work_type"].astype("string").str.strip().str.title()
    given = given.replace({"Full-Time": "Full-time", "Part-Time": "Part-time"})
    text = df["title"].astype("string").fillna("") + " " + df["description"].astype("string").fillna("").str[:500]
    return given.fillna(_infer(text, WORK_TYPE_RULES)).fillna("Not specified")


def extract_skills(df: pd.DataFrame) -> pd.DataFrame:
    """Long table (job_id, skill) from title + description + skills_desc text."""
    text = (df["title"].fillna("") + " " + df["description"].fillna("") + " "
            + df["skills_desc"].fillna("")).astype(str)
    rows = []
    for name, pat in SKILL_PATTERNS.items():
        hits = df.loc[text.str.contains(pat, regex=True), "job_id"]
        rows.append(pd.DataFrame({"job_id": hits.values, "skill": name}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["job_id", "skill"])


def _to_datetime(s: pd.Series) -> pd.Series:
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().mean() > 0.5:  # LinkedIn stores epoch milliseconds
        return pd.to_datetime(num, unit="ms", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


# ---------------------------------------------------------------- main transform
def transform(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    log = {"rows_in": len(raw)}
    df = raw.reindex(columns=POSTING_COLUMNS).copy()

    df["job_id"] = pd.to_numeric(df["job_id"], errors="coerce")
    df = df.dropna(subset=["job_id"]).astype({"job_id": "int64"})
    before = len(df)
    df = df.drop_duplicates("job_id")
    log["duplicate_job_ids_removed"] = before - len(df)

    df["title"] = clean_title(df["title"])
    df["company_name"] = df["company_name"].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    df = df.dropna(subset=["title"])

    # near-duplicates: same company + title + location re-posted
    before = len(df)
    df = (df.assign(_t=_to_datetime(df["listed_time"]))
            .sort_values("_t", ascending=False)
            .drop_duplicates(["company_name", "title", "location"])
            .drop(columns="_t"))
    log["reposted_duplicates_removed"] = before - len(df)

    df = df.join(parse_location(df["location"]))
    df = df.join(annual_salary(df))
    df["experience_level"] = experience_level(df)
    df["work_type"] = work_type(df)
    df["job_family"] = job_family(df["title"])

    remote = df["remote_allowed"].astype("string").str.lower().isin(["1", "1.0", "true", "yes"])
    remote |= df["location"].astype("string").str.contains("remote", case=False, na=False)
    remote |= df["title"].str.contains(r"\bremote\b", case=False, na=False)
    df["is_remote"] = remote

    df["listed_date"] = _to_datetime(df["listed_time"]).dt.normalize()
    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0).astype(int)
    df["applies"] = pd.to_numeric(df["applies"], errors="coerce").fillna(0).astype(int)
    df["apply_rate"] = np.where(df["views"] > 0, df["applies"] / df["views"], np.nan)

    skills = extract_skills(df)
    df["skill_count"] = df["job_id"].map(skills.groupby("job_id").size()).fillna(0).astype(int)

    log["rows_out"] = len(df)
    log["salary_disclosed_pct"] = round(float(df["salary_disclosed"].mean()), 4)
    log["skill_mentions"] = len(skills)
    return df, skills, log
