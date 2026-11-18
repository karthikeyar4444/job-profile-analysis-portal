"""Data-quality scorecard, computed on the raw and the cleaned data.

Each check returns the share of rows that pass (0-1). The overall score is the mean of
all checks, so "before vs after" shows how much the ETL improved the data.
"""
from __future__ import annotations

import pandas as pd

from .config import ANNUAL_SALARY_RANGE, PAY_PERIOD_TO_ANNUAL, US_STATES

STATE_NAMES = {v.lower() for v in US_STATES.values()}


def _annualised(df: pd.DataFrame) -> pd.Series:
    if "salary_annual" in df:
        return df["salary_annual"]
    sal = df["med_salary"].fillna((df["min_salary"] + df["max_salary"]) / 2)
    mult = df["pay_period"].astype("string").str.upper().map(PAY_PERIOD_TO_ANNUAL)
    return sal * mult


def _has_valid_state(df: pd.DataFrame) -> pd.Series:
    if "state_code" in df:
        return df["state_code"].notna()
    loc = df["location"].astype("string").fillna("")
    last = loc.str.split(",").str[-1].str.strip()
    return last.isin(US_STATES.keys()) | last.str.lower().isin(STATE_NAMES)


def scorecard(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    title = df["title"].astype("string")
    salary = _annualised(df)
    has_salary = salary.notna()
    lo, hi = ANNUAL_SALARY_RANGE
    checks = {
        "unique_job_id": 1 - df["job_id"].duplicated().mean(),
        "unique_posting_content": 1 - df.duplicated(["company_name", "title", "location"]).mean(),
        "title_present_and_clean": (title.notna() & (title.str.strip() == title)
                                    & (title.str.len() > 2)).mean(),
        "company_present": df["company_name"].notna().mean(),
        "location_has_valid_state": _has_valid_state(df).mean(),
        # placeholder values like "Not specified" do NOT count as present
        "experience_level_present": (df["experience_level"].ne("Not specified").mean()
                                     if "experience_level" in df
                                     else df["formatted_experience_level"].notna().mean()),
        "salary_valid_when_present": (salary[has_salary].between(lo, hi).mean()
                                      if has_salary.any() else 1.0),
        "work_type_present": (df["work_type"].ne("Not specified").mean() if "work_type" in df
                              else df["formatted_work_type"].notna().mean()),
    }
    checks = {k: round(float(v), 4) for k, v in checks.items()}
    return {
        "label": label,
        "rows": n,
        "checks": checks,
        "overall_score": round(sum(checks.values()) / len(checks), 4),
    }


def compare(before: dict, after: dict) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"Rows: **{before['rows']:,}** raw -> **{after['rows']:,}** after cleaning",
        "",
        "| Check | Raw | Cleaned |",
        "|---|---|---|",
    ]
    for k in before["checks"]:
        lines.append(f"| {k} | {before['checks'][k]:.1%} | {after['checks'][k]:.1%} |")
    b, a = before["overall_score"], after["overall_score"]
    lines += [
        f"| **Overall score** | **{b:.1%}** | **{a:.1%}** |",
        "",
        f"Overall quality improved by **{(a - b) * 100:.1f} percentage points** "
        f"(**{(a - b) / b:.1%}** relative).",
    ]
    return "\n".join(lines)
