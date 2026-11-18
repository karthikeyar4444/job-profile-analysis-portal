import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from jobportal.load import build_star_schema  # noqa: E402
from jobportal.quality import scorecard  # noqa: E402
from jobportal.transform import (annual_salary, clean_title, job_family,  # noqa: E402
                                 parse_location, transform)
from make_sample_data import make  # noqa: E402


def test_clean_title():
    s = clean_title(pd.Series(["  Data Analyst (Remote) ", "Nurse - URGENT HIRING", "x"]))
    assert s.tolist()[:2] == ["Data Analyst", "Nurse"]
    assert pd.isna(s.iloc[2])


def test_salary_annualised_and_filtered():
    df = pd.DataFrame({"min_salary": [40, None, 50_000], "med_salary": [None, 7000, None],
                       "max_salary": [60, None, 9_999_999], "pay_period": ["HOURLY", "MONTHLY", "YEARLY"],
                       "currency": ["USD", "USD", "USD"]})
    out = annual_salary(df)
    assert out.loc[0, "salary_annual"] == 50 * 2080
    assert out.loc[1, "salary_annual"] == 7000 * 12
    assert pd.isna(out.loc[2, "salary_annual"])  # junk max -> invalid


def test_location_parsing():
    loc = parse_location(pd.Series(["Fairfax, VA", "Arlington, Virginia", "California", "Remote"]))
    assert loc["state_code"].tolist()[:3] == ["VA", "VA", "CA"]
    assert pd.isna(loc.loc[3, "state_code"])


def test_job_family():
    fam = job_family(pd.Series(["Senior Data Scientist", "Data Analyst", "Registered Nurse"]))
    assert fam.tolist() == ["Data Science & ML", "Data & Business Analytics", "Healthcare"]


def test_end_to_end_improves_quality_and_builds_schema():
    raw = make(3000)
    postings, skills, log = transform(raw)
    assert postings["job_id"].is_unique
    assert scorecard(postings, "after")["overall_score"] > scorecard(raw, "before")["overall_score"]
    tables = build_star_schema(postings, skills)
    fact = tables["fact_job_postings"]
    assert len(fact) == len(postings)
    assert fact["company_id"].isin(tables["dim_company"]["company_id"]).all()
    assert tables["bridge_job_skill"]["job_id"].isin(fact["job_id"]).all()
