import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobportal.live.store import skill_trends, update  # noqa: E402
from jobportal.live.usajobs import parse_items  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def _items(name):
    return json.loads((FIX / name).read_text())["SearchResult"]["SearchResultItems"]


def test_parse_flattens_usajobs_items():
    df = parse_items(_items("usajobs_sample.json"))
    assert len(df) == 60 and df["id"].is_unique
    assert {"title", "agency", "salary_min", "skills", "remote", "url"} <= set(df.columns)
    assert (df["salary_max"] >= df["salary_min"]).all()
    assert df["skills"].str.contains("Python").any()


def test_hourly_pay_is_annualised():
    item = _items("usajobs_sample.json")[0]
    item["MatchedObjectDescriptor"]["PositionRemuneration"] = [
        {"MinimumRange": "40.00", "MaximumRange": "50.00", "RateIntervalCode": "PH"}]
    row = parse_items([item]).iloc[0]
    assert row["salary_min"] == 40 * 2087


def test_daily_update_tracks_new_closed_and_is_idempotent(tmp_path):
    day1, day2 = parse_items(_items("usajobs_sample.json")), parse_items(_items("usajobs_sample_day2.json"))
    m1 = update(day1, tmp_path, "2026-11-20")
    m2 = update(day2, tmp_path, "2026-11-21")
    m2_again = update(day2, tmp_path, "2026-11-21")  # rerun same day
    assert m1["new_postings"] == 60
    assert m2["new_postings"] == 8 and m2["closed_since_last_run"] == 10
    assert m2_again == m2
    hist = pd.read_csv(tmp_path / "postings.csv", dtype={"id": str})
    assert len(hist) == 68 and hist["id"].is_unique
    assert len(pd.read_csv(tmp_path / "daily_metrics.csv")) == 2
    still_open = hist[hist["last_seen"] == "2026-11-21"]
    assert len(still_open) == 58 and (still_open["first_seen"] <= "2026-11-21").all()


def test_skill_trends(tmp_path):
    update(parse_items(_items("usajobs_sample.json")), tmp_path, "2026-11-20")
    update(parse_items(_items("usajobs_sample_day2.json")), tmp_path, "2026-11-21")
    tr = skill_trends(pd.read_csv(tmp_path / "daily_skills.csv"))
    assert {"skill", "share_now", "change_pts"} <= set(tr.columns) and len(tr) > 5
