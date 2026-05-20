# job-bot

Playwright-based job application automation for two profiles: **muhammad** and **razia**.

Runs as a **desktop app** (FastAPI backend + React UI) or as a plain CLI.

---

## Desktop app — quick start

```bash
# 1. Create Python venv and install dependencies
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. Build the UI (requires Node 18+)
cd ui && npm install && npm run build && cd ..

# 3. Launch — opens browser automatically at http://localhost:8099
python3 launch.py
```

**Dev mode** (hot-reload UI + live API):
```bash
python3 launch.py --dev           # starts Vite on :5173, API on :8099
cd ui && npm run dev              # in a second terminal
```

**Build a standalone executable** (no Python needed):
```bash
python3 build_app.py              # outputs dist/JobBot (macOS/Linux) or dist/JobBot.exe
```

---

## CLI-only quick start

```bash
pip install -r requirements.txt
playwright install chromium

# Discover jobs from resume analysis and apply (Muhammad)
python3 main.py --profile muhammad --discover

# Razia — discover and apply with review before each submit
python3 main.py --profile razia --discover --review

# Dry-run first (fills forms, never submits)
python3 main.py --profile muhammad --discover --dry-run --limit 5
```

---

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | `muhammad` | Which profile to run (`muhammad` or `razia`) |
| `--discover` | off | Auto-discover jobs from resume analysis before applying |
| `--review` | off | Pause and ask y/n/q before each submit |
| `--limit N` | 50 | Stop after N applications this session |
| `--dry-run` | off | Fill every field but skip submit |
| `--min-score F` | 0.05 | Skip only when TF-IDF score < F **and** fit = Low Fit |
| `--companies-only` | off | Only search Tier 1 company career pages (skip Indeed/LinkedIn/Google) |
| `--tier-max N` | 4 | Search up to tier N (1=companies, 2=+Indeed, 3=+LinkedIn, 4=+Google) |
| `--start-id N` | 1 | Skip jobs with ID < N in jobs.csv |
| `--job-id N` | — | Process only this one job ID |

---

## Apply-everything behavior

The bot applies to **every** job regardless of:
- Salary (above or below preference)
- Seniority (Senior/Staff/Lead/Director/VP)
- Years of experience required
- Location (remote, hybrid, on-site, any city)
- Fit score

The only hard skips are:
- Duplicate URL (already in results log)
- 404 / closed/expired posting
- Technical navigation error
- Score below `--min-score` **and** fit label is "Low Fit" (opt-in, default 0.05)

---

## Tiered job discovery

When `--discover` is set, the bot searches in this priority order:

| Tier | Source | Description |
|------|--------|-------------|
| 1 | Direct company career pages | Microsoft, Google, IBM, JPMorgan, Bloomberg, CrowdStrike, etc. |
| 2 | Indeed | Full-time filtered, sorted by date |
| 3 | LinkedIn | Easy Apply filter (non-Easy-Apply jobs handled via redirect) |
| 4 | Google Jobs | Last resort fallback |

Cross-platform duplicates (same company + title found on multiple sources) are deduplicated, keeping the Tier 1 version.

Use `--companies-only` to run only Tier 1 (best quality, avoids job boards).
Use `--tier-max 2` to run Tiers 1 + 2 (companies + Indeed only), etc.

---

## Application handling — all scenarios

**Scenario A — Direct form (Greenhouse, Lever, Workday, Ashby, iCIMS, Taleo):**
Form is on the current page. Fills all fields, uploads resume, submits.

**Scenario B — "Apply on Company Site" redirect (from Indeed/LinkedIn):**
Clicks the redirect button, switches to the new tab, detects the ATS platform, and applies there.

**Scenario C — LinkedIn Easy Apply:**
Multi-step modal. Fills contact info, replaces resume, answers screening questions, submits.

**Scenario D — LinkedIn non-Easy-Apply:**
Treated as Scenario B — clicks Apply, redirects to company site.

---

## Resume replacement on LinkedIn and Indeed

Both platforms store a previously uploaded resume on the account. The bot **always replaces** the stored resume with the job-specific best-match PDF before submitting. Falls back gracefully if the file input cannot be found (logs `failed_used_default`).

---

## TF-IDF resume selection

For each job, all resumes in `resumes/{profile}/` are scored against the full job description using TF-IDF cosine similarity (bigrams, sublinear TF). The highest-scoring resume is selected.

| Fit label | Score |
|-----------|-------|
| Strong Fit | ≥ 0.65 |
| Good Fit | ≥ 0.45 |
| Possible Fit | ≥ 0.30 |
| Stretch | ≥ 0.15 |
| Low Fit | < 0.15 |

Fit labels are **for logging only** — they never block an application.

Company-specific overrides (InStride, Deloitte, IBM sub-routing) fire before TF-IDF when the company name is recognized.

---

## Cover letter auto-generation

A short cover letter is generated per job from the top 3 TF-IDF keywords shared between the job description and the selected resume:

> "I am applying for the Systems Administrator role at Acme Corp. My background in azure, powershell, active directory aligns with your requirements. I would welcome the opportunity to discuss how I can contribute to your team."

Filled into any "cover letter", "why are you interested", or open text field.

---

## Cookie / popup auto-dismissal

Before interacting with any page, the bot automatically dismisses:
- Cookie consent banners ("Accept All", "I Agree", etc.)
- Newsletter and notification popups
- Generic modal overlays

If dismissal fails, the bot logs it and continues.

---

## Duplicate prevention

- URLs are normalized (tracking params stripped) before comparison
- Cross-platform duplicates are matched by normalized (company, title) pair
- All applied URLs are tracked in `output/results_{profile}.csv` across sessions

---

## Review mode

`--review` prints a panel before each submit:

```
┌──────────────────────────────────────────────────────────────┐
│  Company:   Acme Corp                                        │
│  Title:     Systems Administrator                            │
│  Platform:  greenhouse                                       │
│  Salary:    $85,000 (above_target)                           │
│  Resume:    C2_Systems_Administrator.pdf                     │
│  Score:     0.51 — Good Fit                                  │
│  Keywords:  azure, powershell, active directory              │
│  URL:       https://boards.greenhouse.io/acme/jobs/123       │
└──────────────────────────────────────────────────────────────┘
  Apply? (y/n/q):
```

---

## Results logging

Every job attempt is written to two files:

| File | Format |
|------|--------|
| `output/results_{profile}.csv` | CSV, one row per job |
| `output/results_{profile}.jsonl` | JSONL, one JSON object per job |

Fields: timestamp, profile, company, title, location, salary (parsed + label),
job URL, final URL, source tier, source, platform, ATS platform, apply method,
selected resume, TF-IDF score, fit label, matched keywords,
resume replaced (yes/no + method), cover letter used, status, screenshot path, error notes.

Screenshots saved to `output/screenshots/` as `{timestamp}_{company}_{title}_{suffix}.png`.

---

## Run summary

Printed at the end of every run:

```
  Jobs discovered by tier:
    Direct company pages: 12
    Indeed: 8
    LinkedIn: 15
    Google Jobs: 3

  Duplicates skipped (already applied): 4
  Jobs scored: 34

  Applications attempted:
    Total: 34
    direct_form: 20
    easy_apply: 10
    company_site_redirect: 4

  Submitted: 31
    Resume replaced successfully: 28
    Used account default resume: 3
  Submit failed: 3
  Manual CAPTCHA solved: 1
  Errors: 0
  Dry run (not submitted): 0

  By fit label:
    Strong Fit: 4
    Good Fit: 11
    Possible Fit: 9
    Stretch: 7
    Low Fit: 3

  Top 10 by resume score: ...
```

---

## Folder structure

```
job-bot/
├── main.py                  # CLI orchestrator
├── form_filler.py           # Field detection, form filling, resume replacement
├── resume_selector.py       # TF-IDF resume scoring + selection
├── job_finder.py            # Tiered job discovery (4 tiers)
├── jobs.csv                 # Manual job queue
├── launch.py                # Desktop app entry point
├── build_app.py             # PyInstaller packager
├── requirements.txt
├── api/                     # FastAPI backend
│   ├── main.py              # App factory + CORS + static serving
│   ├── bot_runner.py        # Background thread wrapper + WebSocket events
│   ├── security.py          # Per-process token + Fernet encryption
│   ├── websocket.py         # /ws/logs WebSocket endpoint
│   └── routers/             # bot, jobs, resumes, profiles, settings
├── ui/                      # React + Vite + Tailwind frontend
│   ├── src/
│   │   ├── pages/           # Dashboard, Queue, History, Resumes, Analytics,
│   │   │                    #   InterviewTracker, Profiles, Settings
│   │   └── components/      # Layout, Onboarding, StartModal, StatusBadge
│   └── dist/                # Built static files (served by FastAPI)
├── config/
│   ├── muhammad_profile.json
│   └── razia_profile.json
├── resumes/
│   ├── muhammad/            # 39+ resume PDFs
│   └── razia/               # 8 resume PDFs
├── browser_profile/         # Persistent Playwright sessions (gitignored)
└── output/                  # Results CSV/JSONL + screenshots (gitignored)
```

---

## Adding jobs manually

Edit `jobs.csv`:

```csv
id,url,company,title,priority,notes
6,https://boards.greenhouse.io/acme/jobs/12345,Acme Corp,Backend Engineer,HIGH,Remote $120K
```

The `notes` field is parsed for salary (for logging only — never blocks application).

---

## Profile config

`config/muhammad_profile.json` and `config/razia_profile.json` contain personal info
used to fill application forms: name, email, phone, address, LinkedIn, work authorization,
EEO fields, salary expectations.
