# Job Bot

An autonomous job application agent built with Python and React. Point it at your resumes, set your profile, and it finds relevant jobs, scores each one against your background, picks the best resume, fills out the forms, and submits — or routes anything sensitive to a human review queue.

**Stack:** Python · Playwright · FastAPI · React · TF-IDF · WebSockets · Tailwind CSS

---

## What it does

1. **Discovers jobs** from Indeed, LinkedIn, Greenhouse, Lever, Workday, and other open-apply platforms (no login-wall sites)
2. **Scores every job** against all your resumes using TF-IDF cosine similarity — picks the best match
3. **Fills the entire application** — contact info, work authorization, EEO fields, cover letter, salary, file upload
4. **Submits automatically**, or pauses for human review when anything sensitive comes up (SSN, DOB, bank info, unusual criminal questions)
5. **Tracks everything** — every attempt, resume used, score, status, screenshot, and flag logged to CSV + JSONL

---

## Safety first

The bot will never:
- Fill in SSN, passport number, driver's license, date of birth, or bank details
- Bypass a CAPTCHA — it pauses and waits for you to solve it
- Guess on criminal history questions that go beyond the standard "convicted of a felony" pattern
- Auto-answer bot-trap questions ("If you are an AI, type X...")
- Apply to sites that require creating a company-specific account
- Submit to jobs that look like scams (payment requests, WhatsApp-only contact, unrealistic pay)
- Apply to the same job twice across sessions

Anything flagged routes to a **Review Queue** in the UI where you can inspect it, view the job, and dismiss or handle it yourself.

---

## UI

A local web app at `http://localhost:8099` with full control over the bot:

| Page | What it does |
|------|-------------|
| Dashboard | Start/stop/pause the bot, live log stream, session stats |
| Job Queue | Add, import, and manage jobs to apply to |
| History | Full application history with status filters and CSV export |
| Resumes | Upload and score resumes against a job description |
| Analytics | Submission trends, fit-label breakdown, platform stats |
| Interview Tracker | Kanban board for tracking applications post-submission |
| Review Queue | Applications flagged for human review |
| Profiles | Manage candidate profiles |
| Settings | Browser config, session limits, blacklist, API keys |

---

## Quick start

```bash
# 1. Set up Python environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. Build the UI  (requires Node 18+)
cd ui && npm install && npm run build && cd ..

# 3. Copy the example profile and fill in your details
cp config/profile.example.json config/yourname_profile.json

# 4. Add your resume PDFs
mkdir -p resumes/yourname
# drop your PDF resumes in there

# 5. Launch — opens at http://localhost:8099
python3 launch.py
```

---

## CLI usage

```bash
# Discover jobs and apply
python3 main.py --profile yourname --discover

# Review each application before submitting
python3 main.py --profile yourname --discover --review

# Dry run — fills every form but never submits (great for testing)
python3 main.py --profile yourname --discover --dry-run --limit 5
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | — | Profile name matching `config/{name}_profile.json` |
| `--discover` | off | Auto-discover jobs from resume analysis |
| `--review` | off | Pause and ask y/n/q before each submit |
| `--limit N` | 50 | Max applications per session |
| `--dry-run` | off | Fill forms but never submit |
| `--min-score F` | 0 | Skip if TF-IDF score < F **and** fit = Low Fit |
| `--tier-max N` | 3 | Discovery depth: 1=Indeed, 2=+LinkedIn, 3=+Google, 4=+ATS boards |
| `--start-id N` | 1 | Resume from job ID N in jobs.csv |
| `--job-id N` | — | Run a single specific job by ID |

---

## How resume selection works

Every job's full description is scored against all your resumes using **TF-IDF cosine similarity** (bigrams, sublinear TF weighting). The highest-scoring resume wins and gets uploaded with a professional filename.

| Label | Score |
|-------|-------|
| Strong Fit | ≥ 0.65 |
| Good Fit | ≥ 0.45 |
| Possible Fit | ≥ 0.30 |
| Stretch | ≥ 0.15 |
| Low Fit | < 0.15 |

Fit labels are logged and shown in the dashboard — they don't block applications unless you set `--min-score`.

---

## Job discovery tiers

| Tier | Source | Notes |
|------|--------|-------|
| 1 | Indeed | Full-time, sorted by date |
| 2 | LinkedIn | Easy Apply + redirect handling |
| 3 | Google Jobs | Finds Greenhouse/Lever/Workday links |
| 4 | Company ATS boards | Direct Greenhouse/Lever/Workday pages |

Only **open-apply platforms** are used — no job boards that require a company-specific account to apply (Taleo single-sign-on portals, internal career portals, etc.).

---

## What gets logged

Every attempt writes one row to `output/results_{profile}.csv` and one line to `output/results_{profile}.jsonl`:

```
timestamp, profile, company, title, location, salary, job_url, platform,
apply_method, selected_resume, tfidf_score, fit_label, matched_keywords,
resume_replaced, cover_letter_used, status, screenshot_path, error_notes
```

Status values: `submitted` · `submitted_manually` · `dry_run` · `needs_review` · `skipped_scam` · `skipped_low_fit` · `skipped_low_salary` · `auth_wall` · `button_not_found` · `submit_failed` · `error`

---

## Profile config

Copy `config/profile.example.json` and fill in your details:

```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane@example.com",
  "phone": "5551234567",
  "city": "New York",
  "state": "NY",
  "zip": "10001",
  "linkedin": "https://linkedin.com/in/janesmith",
  "authorized_to_work": "Yes",
  "require_sponsorship": "No",
  "salary_minimum": 80000,
  "salary_number": 90000,
  "years_experience": "4"
}
```

Profile files and resumes are in `.gitignore` and never committed.

---

## Adding jobs manually

Paste URLs into the Job Queue page in the UI, or edit `jobs.csv` directly:

```csv
id,url,company,title,priority,notes
1,https://boards.greenhouse.io/acme/jobs/12345,Acme Corp,Backend Engineer,HIGH,Remote $120K
```

The `notes` field is parsed for salary information (logged only — never blocks an application).

---

## Running the tests

```bash
python tests/test_bot.py
```

96 tests covering every safety invariant: sensitive field classification, scam detection, deduplication, salary guards, URL normalization, EEO handling, and PII audit of all source files.

---

## Project structure

```
job-bot/
├── main.py                   # CLI entry point
├── form_filler.py            # Form detection, field filling, file upload
├── resume_selector.py        # TF-IDF resume scoring and selection
├── job_finder.py             # Tiered job discovery
├── safety.py                 # Sensitive field classification, scam detection
├── jobs.csv                  # Job queue (gitignored)
├── launch.py                 # Desktop app launcher
├── tests/
│   └── test_bot.py           # 96-test safety and logic audit suite
├── api/
│   ├── main.py               # FastAPI app + static serving
│   ├── bot_runner.py         # Background thread + WebSocket events
│   ├── security.py           # Session token + Fernet encryption
│   └── routers/              # bot, jobs, resumes, profiles, settings
├── ui/                       # React + Vite + Tailwind
│   └── src/pages/            # Dashboard, History, Queue, Resumes,
│                             #   Analytics, Tracker, Review, Profiles, Settings
├── config/
│   └── profile.example.json  # Template — copy and fill in your details
├── resumes/                  # Your resume PDFs (gitignored)
├── browser_profile/          # Persistent browser sessions (gitignored)
└── output/                   # Results, screenshots (gitignored)
```

---

## Tech

- **Playwright** — persistent browser context per profile, lock cleanup, crash recovery
- **FastAPI** — async API with WebSocket log streaming and Fernet-encrypted settings
- **React + Vite + Tailwind** — real-time dashboard with live session stats
- **TF-IDF (scikit-learn)** — cosine similarity scoring across all resumes per job
- **Safety module** — 14 sensitive field patterns, 11 scam indicators, EEO prefer-not logic, bot-trap detection
