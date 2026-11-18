"""Extract: read raw job-posting files from local disk, S3 or Azure Blob storage.

pandas reads cloud paths directly when the matching filesystem package is installed:
  s3://bucket/path/postings.csv            -> pip install s3fs
  abfs://container@account.dfs.core.windows.net/postings.csv  -> pip install adlfs
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import POSTING_COLUMNS


def _exists(path: str) -> bool:
    return "://" in str(path) or Path(path).exists()


def read_postings(path: str, nrows: int | None = None) -> pd.DataFrame:
    if not _exists(path):
        raise FileNotFoundError(f"{path} not found - see data/README.md for the download step")
    header = pd.read_csv(path, nrows=0).columns
    usecols = [c for c in POSTING_COLUMNS if c in header]
    missing = sorted(set(POSTING_COLUMNS) - set(usecols))
    if missing:
        print(f"[extract] note: columns not in source, will be empty: {missing}")
    df = pd.read_csv(path, usecols=usecols, nrows=nrows, low_memory=False)
    for col in missing:
        df[col] = pd.NA
    print(f"[extract] {len(df):,} postings read from {path}")
    return df[POSTING_COLUMNS]


def read_skill_tags(job_skills_path: str | None, skills_map_path: str | None) -> pd.DataFrame | None:
    """Optional LinkedIn skill tags (jobs/job_skills.csv + mappings/skills.csv)."""
    if not job_skills_path or not _exists(job_skills_path):
        return None
    tags = pd.read_csv(job_skills_path)
    if skills_map_path and _exists(skills_map_path):
        tags = tags.merge(pd.read_csv(skills_map_path), on="skill_abr", how="left")
    else:
        tags["skill_name"] = tags["skill_abr"]
    print(f"[extract] {len(tags):,} LinkedIn skill tags read")
    return tags[["job_id", "skill_name"]].rename(columns={"skill_name": "skill_category"})
