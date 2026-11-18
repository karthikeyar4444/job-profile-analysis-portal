"""Load: write a Power BI-ready star schema and optionally push it to S3 / Azure Blob."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

FACT_COLUMNS = [
    "job_id", "company_id", "location_id", "date_key", "job_family_id",
    "title", "experience_level", "work_type", "is_remote",
    "min_annual", "max_annual", "salary_annual", "salary_band", "salary_disclosed",
    "views", "applies", "apply_rate", "skill_count",
]


def _dim(df: pd.DataFrame, cols: list[str], key: str) -> pd.DataFrame:
    d = df[cols].drop_duplicates().reset_index(drop=True)
    d.insert(0, key, range(1, len(d) + 1))
    return d


def build_star_schema(postings: pd.DataFrame, skills: pd.DataFrame) -> dict[str, pd.DataFrame]:
    p = postings.copy()
    p["company_name"] = p["company_name"].fillna("Unknown")
    for c in ("city", "state_code", "state_name"):
        p[c] = p[c].astype("object").where(p[c].notna(), "Unknown")

    dim_company = _dim(p, ["company_name"], "company_id")
    dim_location = _dim(p, ["city", "state_code", "state_name", "country"], "location_id")
    dim_family = _dim(p, ["job_family"], "job_family_id")

    p = (p.merge(dim_company, on="company_name")
          .merge(dim_location, on=["city", "state_code", "state_name", "country"])
          .merge(dim_family, on="job_family"))
    p["date_key"] = p["listed_date"].dt.strftime("%Y%m%d").astype("Int64")

    dates = p["listed_date"].dropna()
    if len(dates):
        rng = pd.date_range(dates.min(), dates.max(), freq="D")
        dim_date = pd.DataFrame({
            "date_key": rng.strftime("%Y%m%d").astype(int), "date": rng.date,
            "year": rng.year, "month": rng.month, "month_name": rng.strftime("%b"),
            "week": rng.isocalendar().week.values, "weekday": rng.strftime("%a"),
        })
    else:
        dim_date = pd.DataFrame(columns=["date_key", "date", "year", "month", "month_name", "week", "weekday"])

    dim_skill = pd.DataFrame({"skill": sorted(skills["skill"].unique())})
    dim_skill.insert(0, "skill_id", range(1, len(dim_skill) + 1))
    bridge = skills.merge(dim_skill, on="skill")[["job_id", "skill_id"]].drop_duplicates()
    bridge = bridge[bridge["job_id"].isin(p["job_id"])]

    return {
        "fact_job_postings": p[FACT_COLUMNS].sort_values("job_id"),
        "dim_company": dim_company,
        "dim_location": dim_location,
        "dim_job_family": dim_family,
        "dim_date": dim_date,
        "dim_skill": dim_skill,
        "bridge_job_skill": bridge,
    }


def write_tables(tables: dict[str, pd.DataFrame], out_dir: str, fmt: str = "csv") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, df in tables.items():
        path = out / f"{name}.{fmt}"
        if fmt == "parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False)
        paths.append(path)
        print(f"[load] {name:<20} {len(df):>8,} rows -> {path}")
    return paths


def upload_s3(paths: list[Path], bucket: str, prefix: str = "job-portal/processed") -> None:
    import boto3  # pip install boto3 ; credentials from env / ~/.aws

    s3 = boto3.client("s3")
    for p in paths:
        key = f"{prefix}/{p.name}"
        s3.upload_file(str(p), bucket, key)
        print(f"[load] uploaded s3://{bucket}/{key}")


def upload_azure(paths: list[Path], container: str, prefix: str = "job-portal/processed") -> None:
    from azure.storage.blob import BlobServiceClient  # pip install azure-storage-blob

    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client = BlobServiceClient.from_connection_string(conn).get_container_client(container)
    for p in paths:
        with open(p, "rb") as fh:
            client.upload_blob(f"{prefix}/{p.name}", fh, overwrite=True)
        print(f"[load] uploaded azure://{container}/{prefix}/{p.name}")
