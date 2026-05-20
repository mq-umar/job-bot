# job-bot

Playwright-based job application automation for two profiles: **muhammad** and **razia**.

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Apply to jobs in jobs.csv (Muhammad, live)
python3 main.py --profile muhammad

# Apply to jobs in jobs.csv (Razia, live)
python3 main.py --profile razia

# Dry-run — fills every field but never clicks Submit
python3 main.py --profile muhammad --dry-run --limit 10

# Review mode — pause and show a panel before each submit
python3 main.py --profile muhammad --review

# Auto-discover new jobs from resumes, then apply
python3 main.py --profile muhammad --discover
```

---

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | `muhammad` | Which profile to run (`muhammad` or `razia`) |
| `--start-id N` | 1 | Skip jobs with ID < N |
| `--job-id N` | — | Process only this one job ID |
| `--discover` | off | Discover new jobs from resume text, then apply |
| `--review` | off | Show summary panel and pause before each submit |
| `--dry-run` | off | Fill every field but skip submit |
| `--limit N` | unlimited | Stop after N applications this session |
| `--min-score F` | 0.05 | Skip (log as skipped) only when TF-IDF score < F **and** fit = Low Fit |

---

## Apply-everything behavior

The bot applies to **every** job in `jobs.csv` regardless of salary, seniority, or location.
Salary and fit labels are recorded in the results log **for your review only** — they never block an application.

The only hard skips are:
- Duplicate URL (already in results log)
- 404 / closed job page
- Technical navigation error
- Score below `--min-score` threshold **and** fit label is "Low Fit"

---

## TF-IDF resume selection

For each job the bot reads the job description, then scores every resume PDF in
`resumes/{profile}/` using TF-IDF cosine similarity (bigrams, sublinear TF).
It picks the highest-scoring resume and logs:

- **Score** — cosine similarity 0–1
- **Fit label** — Strong Fit / Good Fit / Possible Fit / Stretch / Low Fit
- **Matched keywords** — top shared TF-IDF terms used in the cover letter

| Label | Score |
|-------|-------|
| Strong Fit | ≥ 0.65 |
| Good Fit | ≥ 0.45 |
| Possible Fit | ≥ 0.30 |
| Stretch | ≥ 0.15 |
| Low Fit | < 0.15 |

Company-specific overrides (e.g. InStride, Deloitte, IBM sub-routing) fire before TF-IDF
when the company name is recognized.

---

## Autonomous discovery (`--discover`)

When `--discover` is set the bot:

1. Reads every resume PDF in `resumes/{profile}/`
2. Extracts the most frequent job titles and technical skills using regex patterns
3. Generates LinkedIn Easy Apply and Google Jobs search URLs from those terms
4. Scrapes each URL for job listings
5. Deduplicates against `jobs.csv` and all previous results
6. Appends new jobs to `jobs.csv`
7. Immediately applies to each new job

---

## Duplicate prevention

Every submitted URL is normalized (tracking params stripped) before comparison.
Results are checked against both `jobs.csv` and `output/results_{profile}.csv` so
re-running the bot never double-applies.

---

## Cover letters

Cover letters are generated from the top 3 matched TF-IDF keywords shared between the
job description and the selected resume. Example:

> "I am applying for the Systems Administrator role at Acme Corp. My background in azure,
> powershell, active directory aligns with your requirements. I would welcome the
> opportunity to discuss how I can contribute to your team."

---

## Review mode

`--review` prints a Rich summary panel before each submit:

```
┌─────────────────────────────────────────────────┐
│  Job #12 · Company · Title                      │
│  Resume : C2_Systems_Administrator.pdf          │
│  Score  : 0.512  Fit: Good Fit                  │
│  Keywords: azure, powershell, active directory  │
│  Platform: linkedin                             │
└─────────────────────────────────────────────────┘
Press Enter to submit, 's' to skip, 'q' to quit:
```

---

## Results logging

Every job attempt is appended to two files:

| File | Format |
|------|--------|
| `output/results_{profile}.csv` | CSV, one row per job |
| `output/results_{profile}.jsonl` | JSONL, one JSON object per job |

Fields logged: timestamp, profile, company, title, location, salary (parsed),
salary label (above/at/below/not listed target), job URL, platform, selected resume,
TF-IDF score, fit label, matched keywords, cover letter used, status, screenshot path,
error notes.

Screenshots are saved to `output/screenshots/` as
`{timestamp}_{company}_{title}_{suffix}.png`.

---

## Folder structure

```
job-bot/
├── main.py                  # Orchestrator + CLI
├── form_filler.py           # Field detection + form filling
├── resume_selector.py       # TF-IDF resume scoring + selection
├── job_finder.py            # Autonomous job discovery
├── jobs.csv                 # Job queue (add rows here)
├── requirements.txt
├── config/
│   ├── muhammad_profile.json
│   └── razia_profile.json
├── resumes/
│   ├── muhammad/            # 39+ resume PDFs
│   └── razia/               # 8 resume PDFs
├── browser_profile/         # Persistent Playwright profile (gitignored)
└── output/                  # Results CSV/JSONL + screenshots (gitignored)
```

---

## Adding jobs manually

Edit `jobs.csv`:

```csv
id,url,company,title,priority,notes
6,https://boards.greenhouse.io/acme/jobs/12345,Acme Corp,Backend Engineer,HIGH,Remote $120K
```

The `notes` field is parsed for salary info (for logging only).

---

## Profile config

`config/muhammad_profile.json` and `config/razia_profile.json` contain personal info
(name, email, phone, address, LinkedIn, work authorization, etc.) used to fill
application forms.

---

## Requirements

- Python 3.9+
- `playwright`, `playwright-stealth`, `pandas`, `rich`, `scikit-learn`, `numpy`,
  `pypdf`, `python-dotenv`
