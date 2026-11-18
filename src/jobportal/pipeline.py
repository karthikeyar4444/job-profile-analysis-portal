"""End-to-end ETL: extract -> quality check -> transform -> quality check -> load -> insights.

    python -m jobportal.pipeline --postings data/raw/postings.csv
    python -m jobportal.pipeline --postings s3://my-bucket/raw/postings.csv --upload-s3 my-bucket
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import insights
from .extract import read_postings, read_skill_tags
from .load import build_star_schema, upload_azure, upload_s3, write_tables
from .quality import compare, scorecard
from .transform import transform


def run(postings_path: str, out_dir: str = "data/processed", reports_dir: str = "reports",
        job_skills: str | None = None, skills_map: str | None = None, fmt: str = "csv",
        nrows: int | None = None, upload_s3_bucket: str | None = None,
        upload_azure_container: str | None = None) -> dict:
    t0 = time.time()
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)

    raw = read_postings(postings_path, nrows=nrows)
    q_before = scorecard(raw, "raw")

    postings, skills, log = transform(raw)
    q_after = scorecard(postings, "cleaned")
    print(f"[transform] {json.dumps(log)}")

    tables = build_star_schema(postings, skills)
    tags = read_skill_tags(job_skills, skills_map)
    if tags is not None:
        tables["bridge_job_skill_category"] = tags[tags["job_id"].isin(postings["job_id"])]
    paths = write_tables(tables, out_dir, fmt)

    if upload_s3_bucket:
        upload_s3(paths, upload_s3_bucket)
    if upload_azure_container:
        upload_azure(paths, upload_azure_container)

    (reports / "data_quality_report.md").write_text(compare(q_before, q_after))
    ins = insights.compute(postings, skills)
    (reports / "insights.md").write_text(insights.to_markdown(ins, postings))
    insights.charts(ins, reports / "figures")

    summary = {"etl_log": log, "quality_before": q_before, "quality_after": q_after,
               "runtime_sec": round(time.time() - t0, 1)}
    (reports / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"[quality] overall score {q_before['overall_score']:.1%} -> {q_after['overall_score']:.1%}")
    print(f"[done] {summary['runtime_sec']}s - reports in {reports}/, tables in {out_dir}/")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--postings", default="data/raw/postings.csv")
    p.add_argument("--job-skills", default="data/raw/job_skills.csv",
                   help="optional LinkedIn jobs/job_skills.csv")
    p.add_argument("--skills-map", default="data/raw/skills.csv",
                   help="optional LinkedIn mappings/skills.csv")
    p.add_argument("--out", default="data/processed")
    p.add_argument("--reports", default="reports")
    p.add_argument("--format", choices=["csv", "parquet"], default="csv")
    p.add_argument("--nrows", type=int, default=None, help="read only the first N rows")
    p.add_argument("--upload-s3", metavar="BUCKET")
    p.add_argument("--upload-azure", metavar="CONTAINER")
    a = p.parse_args()
    run(a.postings, a.out, a.reports, a.job_skills, a.skills_map, a.format, a.nrows,
        a.upload_s3, a.upload_azure)


if __name__ == "__main__":
    main()
