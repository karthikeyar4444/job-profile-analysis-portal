"""Live Federal Data & Tech Job Market - updated every morning from the USAJOBS API.

    streamlit run app/live_app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jobportal.live.store import skill_trends  # noqa: E402

DATA = ROOT / "data" / "live"
st.set_page_config(page_title="Live Federal Data & Tech Jobs", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600)
def load():
    if not (DATA / "postings.csv").exists():
        return None, None, None
    postings = pd.read_csv(DATA / "postings.csv", dtype={"id": str, "series_code": str})
    metrics = pd.read_csv(DATA / "daily_metrics.csv", parse_dates=["date"])
    skills = pd.read_csv(DATA / "daily_skills.csv")
    return postings, metrics, skills


postings, metrics, skills = load()
st.title("📈 Live Federal Data & Tech Job Market")
if postings is None:
    st.error("No data yet. Run `python -m jobportal.live.ingest` (see README).")
    st.stop()

latest = metrics["date"].max()
latest_s = latest.strftime("%Y-%m-%d")
open_now = postings[postings["last_seen"] == latest_s].copy()
days_tracked = metrics["date"].nunique()
st.caption(f"Open USAJOBS announcements in 10 data, analytics & IT job series · updated daily by "
           f"GitHub Actions · last update **{latest:%b %d, %Y}** · {days_tracked} day(s) of history")

# ---------------------------------------------------------------- filters
with st.sidebar:
    st.header("Filters")
    series = st.multiselect("Job series", sorted(open_now["series"].dropna().unique()))
    states = st.multiselect("State", sorted(open_now["state"].dropna().unique()))
    remote_only = st.checkbox("Remote only")
    public_only = st.checkbox("Open to the public only",
                              help="Hide announcements limited to current federal employees, veterans, etc.")
f = open_now
if series:
    f = f[f["series"].isin(series)]
if states:
    f = f[f["state"].isin(states)]
if remote_only:
    f = f[f["remote"]]
if public_only:
    f = f[f["who_may_apply"].fillna("").str.contains("public", case=False)]

# ---------------------------------------------------------------- KPIs
today_m = metrics[metrics["date"] == latest].iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Open postings", f"{len(f):,}")
c2.metric("New today", f"{int((f['first_seen'] == latest_s).sum()):,}")
c3.metric("Closed since last run", f"{int(today_m['closed_since_last_run']):,}")
c4.metric("Median starting salary", f"${f['salary_min'].median():,.0f}" if f["salary_min"].notna().any() else "n/a")
c5.metric("Remote", f"{f['remote'].mean():.1%}" if len(f) else "n/a")

tab1, tab2, tab3, tab4 = st.tabs(["Skill demand", "Market over time", "Who's hiring", "New postings"])

with tab1:
    sk = (f.assign(skill=f["skills"].fillna("").str.split(";")).explode("skill")
            .query("skill != ''").groupby("skill").size().sort_values(ascending=False).head(20)
            .rename("postings").reset_index())
    sk["share"] = sk["postings"] / max(len(f), 1)
    fig = px.bar(sk, x="share", y="skill", orientation="h", text="postings",
                 title="Top skills in open postings (share of postings mentioning)",
                 height=max(420, 28 * len(sk)))
    fig.update_traces(textposition="outside", textfont_size=12, cliponaxis=False)
    fig.update_xaxes(tickformat=".0%", title=None)
    fig.update_yaxes(autorange="reversed", title=None, dtick=1)
    st.plotly_chart(fig, use_container_width=True)
    if days_tracked >= 2:
        tr = skill_trends(skills, days=30)
        top = tr.head(15)
        st.plotly_chart(px.bar(top, x="change_pts", y="skill", orientation="h",
                               title=f"Change in share of postings, {top['start_date'].iloc[0]} → "
                                     f"{top['end_date'].iloc[0]} (percentage points)",
                               height=max(420, 28 * len(top)))
                        .update_yaxes(autorange="reversed", title=None, dtick=1),
                        use_container_width=True)
        pick = st.multiselect("Track skills over time", tr["skill"].tolist(),
                              default=tr["skill"].head(4).tolist())
        if pick:
            s = skills[skills["skill"].isin(pick)].assign(date=lambda d: pd.to_datetime(d["date"]))
            st.plotly_chart(px.line(s, x="date", y="share", color="skill", markers=True,
                                    title="Share of open postings mentioning each skill")
                            .update_yaxes(tickformat=".0%"), use_container_width=True)
    else:
        st.info("Skill trends appear after the second daily update.")

with tab2:
    st.plotly_chart(px.line(metrics, x="date", y=["open_postings", "new_postings", "closed_since_last_run"],
                            markers=True, title="Open, new and closed postings per day"),
                    use_container_width=True)
    weekly = (postings.assign(week=pd.to_datetime(postings["posted_date"], errors="coerce")
                              .dt.to_period("W").dt.start_time)
                      .dropna(subset=["week"]).groupby("week").size().rename("postings").reset_index())
    st.plotly_chart(px.bar(weekly.tail(26), x="week", y="postings",
                           title="Announcements published per week (by USAJOBS publication date)"),
                    use_container_width=True)
    st.plotly_chart(px.line(metrics, x="date", y=["median_salary_min", "median_salary_max"], markers=True,
                            title="Median salary range of open postings (USD/year)"),
                    use_container_width=True)

with tab3:
    a, b = st.columns(2)
    ag = f["agency"].value_counts().head(15).rename_axis("agency").reset_index(name="postings")
    a.plotly_chart(px.bar(ag, x="postings", y="agency", orientation="h", title="Top hiring agencies")
                   .update_yaxes(autorange="reversed"), use_container_width=True)
    se = (f.groupby("series").agg(postings=("id", "size"), median_salary=("salary_min", "median"))
            .sort_values("postings", ascending=False).reset_index())
    b.plotly_chart(px.bar(se, x="postings", y="series", orientation="h", hover_data=["median_salary"],
                          title="Postings by job series").update_yaxes(autorange="reversed"),
                   use_container_width=True)
    stc = f["state"].value_counts().head(20).rename_axis("state").reset_index(name="postings")
    st.plotly_chart(px.bar(stc, x="state", y="postings", title="Postings by state (first listed location)"),
                    use_container_width=True)

with tab4:
    new = f[f["first_seen"] == latest_s] if (f["first_seen"] == latest_s).any() else f
    cols = ["title", "agency", "series", "state", "salary_min", "salary_max", "remote",
            "who_may_apply", "close_date", "url"]
    st.dataframe(new.sort_values("posted_date", ascending=False)[cols], hide_index=True,
                 use_container_width=True,
                 column_config={"url": st.column_config.LinkColumn("link", display_text="open"),
                                "salary_min": st.column_config.NumberColumn(format="$%d"),
                                "salary_max": st.column_config.NumberColumn(format="$%d")})

st.caption("Source: USAJOBS Search API (data.usajobs.gov). Skills are matched with a keyword dictionary "
           "over each posting's title, summary, duties and qualifications.")
