"""USAJOBS Search API client and parser (https://developer.usajobs.gov).

Needs two values (free key from developer.usajobs.gov/apirequest):
    USAJOBS_API_KEY   - the Authorization-Key emailed to you
    USAJOBS_EMAIL     - the email you registered with (sent as User-Agent)
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from ..transform import SKILL_PATTERNS

API_URL = "https://data.usajobs.gov/api/search"
PAGE_SIZE = 500  # API maximum

# Federal occupational series for data, analytics and technology work
TECH_SERIES = {
    "2210": "IT Management",
    "1560": "Data Science",
    "1550": "Computer Science",
    "0854": "Computer Engineering",
    "1530": "Statistics",
    "1529": "Mathematical Statistics",
    "1520": "Mathematics",
    "1515": "Operations Research",
    "0110": "Economics",
    "0343": "Management & Program Analysis",
}

# RateIntervalCode -> multiplier to annual pay
PAY_TO_ANNUAL = {"PA": 1, "PH": 2087, "PD": 260, "PW": 52, "BW": 26, "SM": 24, "PM": 12}


class USAJobsError(RuntimeError):
    pass


def fetch_open_postings(api_key: str, email: str, series: list[str] | None = None,
                        max_pages: int = 100, pause_s: float = 0.5) -> list[dict]:
    """Return every open announcement in the given job series (all pages)."""
    series = series or list(TECH_SERIES)
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": api_key}
    items: list[dict] = []
    total = None
    for page in range(1, max_pages + 1):
        query = urllib.parse.urlencode({"JobCategoryCode": ";".join(series),
                                        "ResultsPerPage": PAGE_SIZE, "Page": page, "Fields": "Full"})
        data = _get_json(f"{API_URL}?{query}", headers)
        result = data.get("SearchResult", {})
        total = int(result.get("SearchResultCountAll", 0))
        batch = result.get("SearchResultItems", [])
        items.extend(batch)
        print(f"[usajobs] page {page}: {len(batch)} postings ({len(items):,}/{total:,})")
        if not batch or len(items) >= total:
            break
        time.sleep(pause_s)
    return items


def _get_json(url: str, headers: dict, retries: int = 4) -> dict:
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise USAJobsError("USAJOBS rejected the key (401/403). Check USAJOBS_API_KEY and that "
                                   "USAJOBS_EMAIL is the email you registered with.") from e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(5 * 2 ** attempt)
                continue
            raise USAJobsError(f"USAJOBS error {e.code}: {e.read()[:200]!r}") from e
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(5 * 2 ** attempt)
                continue
            raise USAJobsError(f"could not reach USAJOBS: {e.reason}") from e
    raise USAJobsError("unreachable")


# ---------------------------------------------------------------- parsing
def _first(lst, key=None, default=None):
    if isinstance(lst, list) and lst:
        return lst[0].get(key, default) if key else lst[0]
    return default


def _to_float(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return np.nan


def _skills(text: str) -> str:
    found = [name for name, pat in SKILL_PATTERNS.items() if pat.search(text)]
    return ";".join(sorted(found))


def _is_remote(desc: dict, details: dict) -> bool:
    if str(details.get("RemoteIndicator", "")).lower() == "true":
        return True
    loc = desc.get("PositionLocationDisplay", "") or ""
    return bool(re.search(r"remote|anywhere in the u", loc, re.I))


def parse_items(items: list[dict]) -> pd.DataFrame:
    """Flatten USAJOBS SearchResultItems into one tidy row per announcement."""
    rows = []
    for it in items:
        d = it.get("MatchedObjectDescriptor", {})
        det = d.get("UserArea", {}).get("Details", {}) or {}
        pay = _first(d.get("PositionRemuneration")) or {}
        mult = PAY_TO_ANNUAL.get(pay.get("RateIntervalCode", ""), np.nan)
        lo, hi = _to_float(pay.get("MinimumRange")) * mult, _to_float(pay.get("MaximumRange")) * mult
        locs = d.get("PositionLocation") or []
        cat_code = _first(d.get("JobCategory"), "Code", "")
        text = " ".join(str(x) for x in [
            d.get("PositionTitle", ""), d.get("QualificationSummary", ""), det.get("JobSummary", ""),
            " ".join(det.get("MajorDuties", []) or []), " ".join(det.get("KeyRequirements", []) or []),
        ])
        rows.append({
            "id": str(it.get("MatchedObjectId") or d.get("PositionID")),
            "position_id": d.get("PositionID"),
            "title": (d.get("PositionTitle") or "").strip(),
            "agency": d.get("OrganizationName"),
            "department": d.get("DepartmentName"),
            "series_code": cat_code,
            "series": TECH_SERIES.get(cat_code, _first(d.get("JobCategory"), "Name", "Other")),
            "pay_plan": _first(d.get("JobGrade"), "Code", ""),
            "grade_low": det.get("LowGrade"),
            "grade_high": det.get("HighGrade"),
            "salary_min": round(lo, 0) if pd.notna(lo) else np.nan,
            "salary_max": round(hi, 0) if pd.notna(hi) else np.nan,
            "city": _first(locs, "CityName", ""),
            "state": _first(locs, "CountrySubDivisionCode", ""),
            "n_locations": len(locs),
            "remote": _is_remote(d, det),
            "telework": str(det.get("TeleworkEligible", "")).lower() == "true",
            "schedule": _first(d.get("PositionSchedule"), "Name", ""),
            "who_may_apply": (det.get("WhoMayApply") or {}).get("Name", ""),
            "posted_date": str(d.get("PublicationStartDate", ""))[:10],
            "close_date": str(d.get("ApplicationCloseDate", ""))[:10],
            "url": d.get("PositionURI"),
            "skills": _skills(text),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # same announcement can be listed once per location group - keep one row per id
    return df.drop_duplicates("id").reset_index(drop=True)
