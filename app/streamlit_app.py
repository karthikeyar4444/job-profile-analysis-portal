"""Interactive Job Profile Analysis Portal (Streamlit).

Reads the star-schema tables produced by the ETL pipeline:
    python -m jobportal.pipeline --postings data/raw/postings.csv
    streamlit run app/streamlit_app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"

st.set_page_config(page_title="Job Profile Analysis Portal", layout="wide")


@st.cache_data
def load():
    t = {p.stem: pd.read_csv(p) for p in DATA.glob("*.csv")}
    if "fact_job_postings" not in t:
        return None, None
    f = (t["fact_job_postings"]
         .merge(t["dim_company"], on="company_id")
         .merge(t["dim_location"], on="location_id")
         .merge(t["dim_job_family"], on="job_family_id"))
    f["state_code"] = f["state_code"].replace("Unknown", pd.NA)
    skills = t["bridge_job_skill"].merge(t["dim_skill"], on="skill_id")
    return f, skills


facts, skills = load()
st.title("Job Profile Analysis Portal")
if facts is None:
    st.error(f"No processed data in {DATA}. Run the ETL pipeline first (see README).")
    st.stop()

# ---------------- sidebar filters
with st.sidebar:
    st.header("Filters")
    fam = st.multiselect("Job family", sorted(facts["job_family"].unique()))
    lvl = st.multiselect("Experience level", sorted(facts["experience_level"].unique()))
    states = st.multiselect("State", sorted(facts["state_code"].dropna().unique()))
    remote_only = st.checkbox("Remote-eligible only")

f = facts
if fam:
    f = f[f["job_family"].isin(fam)]
if lvl:
    f = f[f["experience_level"].isin(lvl)]
if states:
    f = f[f["state_code"].isin(states)]
if remote_only:
    f = f[f["is_remote"]]
s = skills[skills["job_id"].isin(f["job_id"])]

# ---------------- KPI row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Postings", f"{len(f):,}")
c2.metric("Median salary", f"${f['salary_annual'].median():,.0f}" if f["salary_annual"].notna().any() else "n/a")
c3.metric("Salary disclosed", f"{f['salary_disclosed'].mean():.0%}")
c4.metric("Remote-eligible", f"{f['is_remote'].mean():.0%}")

tab1, tab2, tab3 = st.tabs(["Skill demand", "Salary trends", "Employment patterns"])

with tab1:
    top = s["skill"].value_counts().head(20).rename_axis("skill").reset_index(name="postings")
    st.plotly_chart(px.bar(top, x="postings", y="skill", orientation="h",
                           title="Top 20 skills").update_yaxes(autorange="reversed"),
                    use_container_width=True)
    pay = (s.merge(f[["job_id", "salary_annual"]], on="job_id").dropna()
           .groupby("skill")["salary_annual"].agg(["median", "count"]).query("count >= 20")
           .sort_values("median", ascending=False).head(15).reset_index())
    st.plotly_chart(px.bar(pay, x="median", y="skill", orientation="h",
                           title="Highest-paying skills (median annual salary)")
                    .update_yaxes(autorange="reversed"), use_container_width=True)

with tab2:
    paid = f.dropna(subset=["salary_annual"])
    st.plotly_chart(px.box(paid, x="job_family", y="salary_annual", points=False,
                           title="Salary distribution by job family"), use_container_width=True)
    st.plotly_chart(px.box(paid, x="experience_level", y="salary_annual", points=False,
                           title="Salary by experience level"), use_container_width=True)

with tab3:
    by_state = (f.dropna(subset=["state_code"]).groupby("state_code")
                .agg(postings=("job_id", "size"), median_salary=("salary_annual", "median"))
                .reset_index())
    st.plotly_chart(px.choropleth(by_state, locations="state_code", locationmode="USA-states",
                                  color="postings", scope="usa", hover_data=["median_salary"],
                                  title="Postings by state"), use_container_width=True)
    col_a, col_b = st.columns(2)
    col_a.plotly_chart(px.pie(f, names="work_type", title="Work type"), use_container_width=True)
    col_b.plotly_chart(px.histogram(f, x="experience_level", title="Experience level"),
                       use_container_width=True)
