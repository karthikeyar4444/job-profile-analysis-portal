"""Generate a SYNTHETIC, deliberately messy postings.csv with the LinkedIn dataset's schema.

Only for smoke-testing the ETL without the real Kaggle download. Never report
insights or quality numbers from this file.

    python scripts/make_sample_data.py --rows 55000 --out data/raw/sample_postings.csv
"""
import argparse

import numpy as np
import pandas as pd

TITLES = {
    "Data Analyst": 85_000, "Senior Data Scientist": 155_000, "Data Engineer": 130_000,
    "Business Intelligence Analyst": 90_000, "Software Engineer": 135_000,
    "Registered Nurse": 82_000, "Sales Representative": 60_000, "Accountant": 72_000,
    "Customer Service Representative": 38_000, "Project Manager": 105_000,
    "Machine Learning Engineer": 165_000, "Warehouse Associate": 36_000,
    "Marketing Coordinator": 55_000, "Cloud Engineer": 140_000, "Data Analyst Intern": 45_000,
    "Mechanical Engineer": 95_000, "Recruiter": 65_000, "Teacher": 58_000,
}
SKILL_TEXT = {
    "Data": ["Python", "SQL", "Power BI", "Tableau", "Excel", "statistics", "ETL", "AWS",
             "Spark", "machine learning", "pandas", "Azure", "Snowflake", "dbt", "Airflow"],
    "Soft": ["communication skills", "leadership", "customer service", "Agile", "Jira",
             "project management", "Salesforce"],
}
LOCATIONS = ["New York, NY", "San Francisco, CA", "Austin, TX", "Fairfax, VA", "Seattle, WA",
             "Chicago, IL", "Boston, MA", "Atlanta, GA", "Denver, CO", "United States",
             "Remote", "California", "Arlington, Virginia", "Dallas-Fort Worth Metroplex",
             "Raleigh, NC", "Phoenix, AZ"]
COMPANIES = [f"Company {i}" for i in range(1, 2500)]
LEVELS = ["Entry level", "Mid-Senior level", "Associate", "Director", "Internship", "Executive"]
WORK = ["Full-time", "Contract", "Part-time", "Temporary", "Internship"]


def make(rows: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    titles = rng.choice(list(TITLES), rows)
    base = np.array([TITLES[t] for t in titles]) * rng.lognormal(0, 0.18, rows)
    period = rng.choice(["YEARLY", "HOURLY", "MONTHLY", None], rows, p=[0.22, 0.10, 0.02, 0.66])
    div = pd.Series(period).map({"YEARLY": 1, "HOURLY": 2080, "MONTHLY": 12}).values
    med = base / np.where(pd.isna(div), 1, div)
    salary_kind = rng.random(rows)
    min_s = np.where(salary_kind < 0.7, med * 0.85, np.nan)
    max_s = np.where(salary_kind < 0.7, med * 1.15, np.nan)
    med_s = np.where(salary_kind >= 0.7, med, np.nan)
    no_pay = pd.isna(period)
    min_s[no_pay] = max_s[no_pay] = med_s[no_pay] = np.nan

    desc = []
    for t in titles:
        pool = SKILL_TEXT["Data"] if any(k in t for k in ("Data", "Intelligence", "Machine", "Cloud", "Software")) \
            else SKILL_TEXT["Soft"]
        k = rng.integers(2, 7)
        desc.append(f"We are hiring a {t}. Requirements: " + ", ".join(rng.choice(pool, k, replace=False))
                    + ". " + rng.choice(["Full-time role.", "Part-time schedule.", "Contract position.", ""]))

    start = pd.Timestamp("2024-03-01").value // 10**6
    df = pd.DataFrame({
        "job_id": rng.integers(10**9, 4 * 10**9, rows),
        "company_name": rng.choice(COMPANIES, rows),
        "title": titles,
        "description": desc,
        "max_salary": max_s, "pay_period": period, "location": rng.choice(LOCATIONS, rows),
        "company_id": rng.integers(1, 2500, rows), "views": rng.poisson(40, rows),
        "med_salary": med_s, "min_salary": min_s,
        "formatted_work_type": rng.choice(WORK, rows, p=[0.8, 0.09, 0.07, 0.02, 0.02]),
        "applies": rng.poisson(6, rows).astype(float),
        "original_listed_time": None,
        "remote_allowed": rng.choice([1.0, np.nan], rows, p=[0.15, 0.85]),
        "formatted_experience_level": rng.choice(LEVELS, rows),
        "skills_desc": None,
        "listed_time": start + rng.integers(0, 60 * 86_400_000, rows),
        "currency": np.where(no_pay, None, "USD"),
    })
    df["original_listed_time"] = df["listed_time"]

    # ---- inject realistic mess
    idx = lambda frac: rng.choice(rows, int(rows * frac), replace=False)
    df.loc[idx(0.30), "formatted_experience_level"] = np.nan
    df.loc[idx(0.12), "formatted_work_type"] = np.nan
    df.loc[idx(0.02), "company_name"] = np.nan
    t = idx(0.08); df.loc[t, "title"] = "  " + df.loc[t, "title"] + " (Remote)  "
    t = idx(0.03); df.loc[t, "title"] = df.loc[t, "title"] + " - URGENT HIRING"
    t = idx(0.01); df.loc[t, "max_salary"] = 9_999_999          # junk salary
    dup = df.sample(int(rows * 0.04), random_state=seed)           # re-posts
    dup = dup.assign(job_id=rng.integers(4 * 10**9, 5 * 10**9, len(dup)))
    exact = df.sample(int(rows * 0.01), random_state=seed + 1)     # exact duplicate rows
    return pd.concat([df, dup, exact], ignore_index=True).sample(frac=1, random_state=seed)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=55_000)
    p.add_argument("--out", default="data/raw/sample_postings.csv")
    a = p.parse_args()
    d = make(a.rows)
    d.to_csv(a.out, index=False)
    print(f"wrote {len(d):,} synthetic rows -> {a.out}")
