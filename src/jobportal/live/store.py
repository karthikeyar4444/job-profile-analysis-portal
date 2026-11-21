"""Keep a growing history of postings plus daily snapshot metrics, as small CSV files.

data/live/postings.csv      one row per announcement ever seen: first_seen / last_seen dates
data/live/daily_metrics.csv one row per day: open, new, closed, median salary, remote share
data/live/daily_skills.csv  one row per day x skill: open postings mentioning the skill

Re-running on the same day replaces that day's rows, so the job is safe to retry.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

POSTINGS = "postings.csv"
METRICS = "daily_metrics.csv"
SKILLS = "daily_skills.csv"


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"id": str, "series_code": str}) if path.exists() else pd.DataFrame()


def update(today: pd.DataFrame, data_dir: str | Path, run_date: str) -> dict:
    """Merge today's open postings into history and append today's metrics."""
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    hist = _read(d / POSTINGS)

    today = today.copy()
    today["first_seen"] = run_date
    today["last_seen"] = run_date
    if not hist.empty:
        # undo a previous run on the same day, so reruns are idempotent
        hist = hist[hist["first_seen"] != run_date]
        hist.loc[hist["last_seen"] == run_date, "last_seen"] = hist.get("prev_last_seen")
        known = hist.set_index("id")["first_seen"]
        today["first_seen"] = today["id"].map(known).fillna(run_date)
        prev_last = hist.set_index("id")["last_seen"]
        today["prev_last_seen"] = today["id"].map(prev_last)
        open_before = set(hist.loc[hist["last_seen"] == hist["last_seen"].max(), "id"]) if len(hist) else set()
        hist = hist[~hist["id"].isin(today["id"])]
    else:
        open_before = set()
    merged = pd.concat([hist, today], ignore_index=True).sort_values(["last_seen", "first_seen", "id"])
    merged.to_csv(d / POSTINGS, index=False)

    new_ids = today.loc[today["first_seen"] == run_date, "id"]
    closed = len(open_before - set(today["id"])) if open_before else 0
    metrics = {
        "date": run_date,
        "open_postings": len(today),
        "new_postings": int(len(new_ids)),
        "closed_since_last_run": int(closed),
        "median_salary_min": float(today["salary_min"].median()) if len(today) else None,
        "median_salary_max": float(today["salary_max"].median()) if len(today) else None,
        "remote_share": round(float(today["remote"].mean()), 4) if len(today) else None,
        "telework_share": round(float(today["telework"].mean()), 4) if len(today) else None,
        "agencies": int(today["agency"].nunique()) if len(today) else 0,
    }
    _upsert(d / METRICS, pd.DataFrame([metrics]), run_date)

    skills = (today.assign(skill=today["skills"].fillna("").str.split(";"))
                   .explode("skill").query("skill != ''")
                   .groupby("skill").size().rename("open_postings").reset_index())
    skills["share"] = (skills["open_postings"] / max(len(today), 1)).round(4)
    skills.insert(0, "date", run_date)
    _upsert(d / SKILLS, skills.sort_values("open_postings", ascending=False), run_date)
    return metrics


def _upsert(path: Path, rows: pd.DataFrame, run_date: str) -> None:
    old = _read(path)
    if not old.empty:
        old = old[old["date"] != run_date]
    pd.concat([old, rows], ignore_index=True).to_csv(path, index=False)


def skill_trends(skills_daily: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Change in each skill's share of open postings between the earliest day in the
    window and the latest day."""
    if skills_daily.empty:
        return skills_daily
    s = skills_daily.copy()
    s["date"] = pd.to_datetime(s["date"])
    latest = s["date"].max()
    window = s[s["date"] >= latest - pd.Timedelta(days=days)]
    first = window["date"].min()
    a = window[window["date"] == first].set_index("skill")["share"]
    b = window[window["date"] == latest].set_index("skill")["share"]
    out = pd.DataFrame({"share_start": a, "share_now": b}).fillna(0)
    out["change_pts"] = ((out["share_now"] - out["share_start"]) * 100).round(2)
    out["start_date"], out["end_date"] = first.date(), latest.date()
    return out.sort_values("share_now", ascending=False).reset_index().rename(columns={"index": "skill"})
