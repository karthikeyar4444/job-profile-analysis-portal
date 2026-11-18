# Power BI Dashboard Guide

The ETL writes a star schema to `data/processed/`. This guide rebuilds the
`Job_Profile_Analysis.pbix` report from those files.

## 1. Load the tables

**Home → Get data → Text/CSV** (or **Folder** pointing at `data/processed`, or
**Amazon S3 / Azure Blob Storage** if you used `--upload-s3` / `--upload-azure`).

Load: `fact_job_postings`, `dim_company`, `dim_location`, `dim_job_family`,
`dim_date`, `dim_skill`, `bridge_job_skill`.

In Power Query set types: `date_key` → Whole number, `dim_date[date]` → Date,
salary columns → Decimal, `is_remote` / `salary_disclosed` → True/False.

## 2. Relationships (Model view)

| From (many) | To (one) | Cardinality | Cross-filter |
|---|---|---|---|
| fact_job_postings[company_id] | dim_company[company_id] | *:1 | Single |
| fact_job_postings[location_id] | dim_location[location_id] | *:1 | Single |
| fact_job_postings[job_family_id] | dim_job_family[job_family_id] | *:1 | Single |
| fact_job_postings[date_key] | dim_date[date_key] | *:1 | Single |
| bridge_job_skill[job_id] | fact_job_postings[job_id] | *:1 | **Both** |
| bridge_job_skill[skill_id] | dim_skill[skill_id] | *:1 | Single |

Mark `dim_date` as the date table (**Table tools → Mark as date table → date**).

## 3. DAX measures

Create a `_Measures` table and paste the measures from [`measures.dax`](measures.dax).

## 4. Report pages

| Page | Visuals |
|---|---|
| **Overview** | KPI cards: Total Postings, Median Salary, % Salary Disclosed, % Remote · line chart Postings by week (`dim_date[date]`) · bar chart Postings by Job Family · slicers: Job Family, Experience Level, State, Work Type |
| **Skill Demand** | Bar chart Top N skills (`dim_skill[skill]` by *Skill Postings*, Top N filter = 20) · bar chart *Median Salary* by skill · matrix Job Family × Skill with *Skill Share %* (conditional-format heat map) |
| **Salary Trends** | Box/column chart *Median Salary* by Experience Level · bar chart *Median Salary* by Job Family · column chart postings by `salary_band` · line chart *Median Salary* by month |
| **Employment Patterns** | Filled map postings by `dim_location[state_name]` · donut Work Type · stacked bar Remote vs On-site by Job Family · table Top 15 companies by postings with median salary |

Theme tip: **View → Themes** and keep one accent colour; use the same slicers on every
page with **View → Sync slicers**.

## 5. Publishing

Save as `powerbi/Job_Profile_Analysis.pbix`, then export screenshots of each page to
`powerbi/screenshots/` and reference them in the main README so recruiters can see the
dashboard without Power BI Desktop.
