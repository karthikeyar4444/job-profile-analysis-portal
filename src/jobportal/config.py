"""Static configuration: expected columns, normalisation rules and skill dictionary."""
from __future__ import annotations

# Columns used from the Kaggle "LinkedIn Job Postings (2023-2024)" postings.csv
POSTING_COLUMNS = [
    "job_id", "company_name", "title", "description", "location",
    "min_salary", "med_salary", "max_salary", "pay_period", "currency",
    "formatted_work_type", "formatted_experience_level", "remote_allowed",
    "views", "applies", "listed_time", "original_listed_time", "skills_desc",
]

# Multiply a salary by this to get an annual figure
PAY_PERIOD_TO_ANNUAL = {
    "YEARLY": 1, "ANNUAL": 1, "MONTHLY": 12, "BIWEEKLY": 26,
    "WEEKLY": 52, "DAILY": 260, "HOURLY": 2080,
}
ANNUAL_SALARY_RANGE = (15_000, 800_000)  # anything outside is treated as invalid

EXPERIENCE_LEVELS = {
    "internship": "Internship", "entry level": "Entry level", "associate": "Associate",
    "mid-senior level": "Mid-Senior level", "director": "Director", "executive": "Executive",
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# Job family rules: first match on the lower-cased title wins (order matters)
JOB_FAMILIES = [
    ("Data Science & ML", ["data scientist", "machine learning", "ml engineer", "ai engineer",
                           "deep learning", "nlp", "computer vision"]),
    ("Data Engineering", ["data engineer", "etl", "big data", "data architect", "analytics engineer"]),
    ("Data & Business Analytics", ["data analyst", "business analyst", "bi analyst",
                                   "business intelligence", "analytics", "reporting analyst"]),
    ("Software Engineering", ["software", "developer", "programmer", "full stack", "backend",
                              "front end", "frontend", "devops", "sre", "site reliability"]),
    ("Cloud & Infrastructure", ["cloud", "network", "system administrator", "systems engineer",
                                "infrastructure"]),
    ("Cybersecurity", ["security", "cyber", "soc analyst", "penetration"]),
    ("Product & Project Mgmt", ["product manager", "project manager", "program manager",
                                "scrum master", "product owner"]),
    ("Healthcare", ["nurse", "rn ", "physician", "therap", "medical", "pharmac", "clinical",
                    "dental", "caregiver", "health"]),
    ("Sales & Marketing", ["sales", "account executive", "marketing", "business development",
                           "account manager", "seo"]),
    ("Finance & Accounting", ["accountant", "accounting", "financial", "finance", "auditor",
                              "tax", "payroll", "controller"]),
    ("Operations & Logistics", ["operations", "warehouse", "logistics", "supply chain",
                                "driver", "inventory", "procurement"]),
    ("Customer Service & Admin", ["customer service", "customer success", "receptionist",
                                  "administrative", "assistant", "support specialist"]),
    ("Engineering (Non-Software)", ["mechanical", "electrical", "civil", "manufacturing engineer",
                                    "process engineer", "engineer"]),
    ("Education", ["teacher", "instructor", "tutor", "professor", "educat"]),
    ("Human Resources", ["recruiter", "human resources", "hr ", "talent acquisition"]),
]

# Skill dictionary: canonical name -> regex (matched case-insensitively on title + description)
SKILLS = {
    "Python": r"\bpython\b", "SQL": r"\bsql\b", "R": r"\bR\b(?:\s+programming|\s*,|\s+and)",
    "Java": r"\bjava\b(?!script)", "JavaScript": r"\bjavascript\b|\bjs\b", "C++": r"c\+\+",
    "C#": r"c#", "Scala": r"\bscala\b", "Go": r"\bgolang\b",
    "Excel": r"\bexcel\b", "Power BI": r"power\s?bi", "Tableau": r"\btableau\b",
    "Looker": r"\blooker\b", "SAS": r"\bsas\b", "SPSS": r"\bspss\b",
    "AWS": r"\baws\b|amazon web services", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|google cloud",
    "Spark": r"\bspark\b|pyspark", "Hadoop": r"\bhadoop\b", "Kafka": r"\bkafka\b",
    "Airflow": r"\bairflow\b", "dbt": r"\bdbt\b", "Snowflake": r"\bsnowflake\b",
    "Databricks": r"\bdatabricks\b", "Docker": r"\bdocker\b", "Kubernetes": r"\bkubernetes\b|\bk8s\b",
    "Git": r"\bgit\b|github", "Linux": r"\blinux\b",
    "Machine Learning": r"machine learning", "Deep Learning": r"deep learning",
    "TensorFlow": r"tensorflow", "PyTorch": r"pytorch", "scikit-learn": r"scikit|sklearn",
    "Pandas": r"\bpandas\b", "NLP": r"\bnlp\b|natural language", "Statistics": r"\bstatistic",
    "ETL": r"\betl\b|\belt\b", "Data Visualization": r"data visuali[sz]ation",
    "MongoDB": r"mongodb", "PostgreSQL": r"postgres", "MySQL": r"mysql", "Oracle": r"\boracle\b",
    "Salesforce": r"salesforce", "SAP": r"\bsap\b", "Jira": r"\bjira\b",
    "Agile": r"\bagile\b|\bscrum\b", "Project Management": r"project management",
    "Communication": r"communication skills", "Leadership": r"\bleadership\b",
    "Customer Service": r"customer service", "React": r"\breact\b", "Node.js": r"node\.?js",
    "REST APIs": r"rest(ful)?\s?api", "Generative AI": r"generative ai|\bllm|gpt",
}
