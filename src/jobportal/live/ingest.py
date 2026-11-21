"""Daily job: fetch open federal data/tech postings from USAJOBS and update the history.

    python -m jobportal.live.ingest                       # uses USAJOBS_API_KEY + USAJOBS_EMAIL
    python -m jobportal.live.ingest --fixture tests/fixtures/usajobs_sample.json   # offline test
Runs every morning on GitHub Actions (.github/workflows/daily_ingest.yml).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from .store import update
from .usajobs import TECH_SERIES, USAJobsError, fetch_open_postings, parse_items


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default="data/live")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="snapshot date (YYYY-MM-DD)")
    p.add_argument("--fixture", help="read a saved USAJOBS JSON response instead of calling the API")
    a = p.parse_args()

    if a.fixture:
        items = json.loads(Path(a.fixture).read_text())["SearchResult"]["SearchResultItems"]
    else:
        _load_dotenv()
        key, email = os.getenv("USAJOBS_API_KEY"), os.getenv("USAJOBS_EMAIL")
        if not key or not email:
            sys.exit("Set USAJOBS_API_KEY and USAJOBS_EMAIL (in .env locally, or as GitHub secrets).")
        try:
            items = fetch_open_postings(key.strip(), email.strip())
        except USAJobsError as e:
            sys.exit(f"[usajobs] {e}")

    today = parse_items(items)
    if today.empty:
        sys.exit("[usajobs] no postings returned - nothing written")
    m = update(today, a.data_dir, a.date)
    print(f"[live] {a.date}: {m['open_postings']:,} open · {m['new_postings']:,} new · "
          f"{m['closed_since_last_run']:,} closed since last run · "
          f"median min salary ${m['median_salary_min']:,.0f} · remote {m['remote_share']:.1%}")
    print(f"[live] series tracked: {', '.join(TECH_SERIES.values())}")


if __name__ == "__main__":
    main()
