# Data

Source: **LinkedIn Job Postings (2023–2024)** on Kaggle
https://www.kaggle.com/datasets/arshkon/linkedin-job-postings

```bash
pip install kaggle          # needs ~/.kaggle/kaggle.json (Kaggle → Settings → API → Create token)
kaggle datasets download -d arshkon/linkedin-job-postings -p data/raw --unzip
```

Then make sure these paths exist (move files if the zip uses sub-folders):

| File | Required |
|---|---|
| `data/raw/postings.csv` | yes |
| `data/raw/job_skills.csv` (from `jobs/`) | optional |
| `data/raw/skills.csv` (from `mappings/`) | optional |

Use `--nrows 50000` on the pipeline to work with a 50K subset.

Raw and processed data are git-ignored. `python scripts/make_sample_data.py` writes a
**synthetic** messy file for smoke tests only — don't report numbers from it.
