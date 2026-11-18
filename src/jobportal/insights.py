"""Workforce / career insights computed from the cleaned data (markdown + charts)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

LEVEL_ORDER = ["Internship", "Entry level", "Associate", "Mid-Senior level", "Director",
               "Executive", "Not specified"]


def compute(postings: pd.DataFrame, skills: pd.DataFrame) -> dict[str, pd.DataFrame]:
    n = len(postings)
    paid = postings[postings["salary_disclosed"]]

    top_skills = (skills["skill"].value_counts().head(20).rename_axis("skill")
                  .reset_index(name="postings"))
    top_skills["share_of_postings"] = (top_skills["postings"] / n).round(4)

    skill_salary = (skills.merge(paid[["job_id", "salary_annual"]], on="job_id")
                    .groupby("skill")["salary_annual"].agg(["median", "count"])
                    .query("count >= 30").sort_values("median", ascending=False).head(15)
                    .round(0).reset_index())

    family = (postings.groupby("job_family")
              .agg(postings=("job_id", "size"),
                   median_salary=("salary_annual", "median"),
                   remote_share=("is_remote", "mean"),
                   avg_skills=("skill_count", "mean"))
              .sort_values("postings", ascending=False).round(2).reset_index())

    level = (postings.groupby("experience_level")
             .agg(postings=("job_id", "size"), median_salary=("salary_annual", "median"))
             .reindex([l for l in LEVEL_ORDER if l in set(postings["experience_level"])])
             .round(0).reset_index())

    states = (postings.dropna(subset=["state_code"]).groupby("state_code")
              .agg(postings=("job_id", "size"), median_salary=("salary_annual", "median"))
              .sort_values("postings", ascending=False).head(15).round(0).reset_index())

    trend = (postings.dropna(subset=["listed_date"])
             .set_index("listed_date").resample("W")["job_id"].count()
             .rename("postings").reset_index())

    return {"top_skills": top_skills, "skill_salary": skill_salary, "job_family": family,
            "experience_level": level, "top_states": states, "weekly_trend": trend}


def _barh(ax, df, x, y, title, fmt=None):
    d = df.iloc[::-1]
    ax.barh(d[y].astype(str), d[x], color="#2f6db5")
    ax.set_title(title, fontsize=11)
    if fmt:
        ax.xaxis.set_major_formatter(fmt)


def charts(ins: dict[str, pd.DataFrame], fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    money = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:.0f}K")

    fig, ax = plt.subplots(figsize=(7, 6))
    _barh(ax, ins["top_skills"], "postings", "skill", "Most in-demand skills (postings mentioning)")
    fig.tight_layout(); fig.savefig(fig_dir / "top_skills.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    _barh(ax, ins["job_family"].dropna(subset=["median_salary"]).sort_values("median_salary", ascending=False),
          "median_salary", "job_family", "Median annual salary by job family", money)
    fig.tight_layout(); fig.savefig(fig_dir / "salary_by_family.png", dpi=150); plt.close(fig)

    if len(ins["skill_salary"]):
        fig, ax = plt.subplots(figsize=(7, 6))
        _barh(ax, ins["skill_salary"], "median", "skill", "Highest-paying skills (median, n>=30)", money)
        fig.tight_layout(); fig.savefig(fig_dir / "salary_by_skill.png", dpi=150); plt.close(fig)

    lvl = ins["experience_level"].dropna(subset=["median_salary"])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(lvl["experience_level"], lvl["median_salary"], color="#2f6db5")
    ax.yaxis.set_major_formatter(money); ax.set_title("Median salary by experience level")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout(); fig.savefig(fig_dir / "salary_by_experience.png", dpi=150); plt.close(fig)

    if len(ins["weekly_trend"]) > 1:
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(ins["weekly_trend"]["listed_date"], ins["weekly_trend"]["postings"], color="#2f6db5")
        ax.set_title("Postings per week")
        fig.tight_layout(); fig.savefig(fig_dir / "weekly_trend.png", dpi=150); plt.close(fig)


def to_markdown(ins: dict[str, pd.DataFrame], postings: pd.DataFrame) -> str:
    md = ["# Workforce & Career Insights", "",
          f"- Postings analysed: **{len(postings):,}**",
          f"- Salary disclosed: **{postings['salary_disclosed'].mean():.1%}** of postings",
          f"- Median disclosed annual salary: **${postings['salary_annual'].median():,.0f}**",
          f"- Remote-eligible: **{postings['is_remote'].mean():.1%}**", ""]
    for name, df in ins.items():
        if name == "weekly_trend":
            continue
        md += [f"## {name.replace('_', ' ').title()}", "", _md_table(df), ""]
    return "\n".join(md)


def _md_table(df: pd.DataFrame) -> str:
    """Small markdown table writer (avoids the optional 'tabulate' dependency)."""
    def fmt(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:.2f}")
        return str(v)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join(fmt(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows])
