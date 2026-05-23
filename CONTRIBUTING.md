# Contributing to job-bot

Thank you for your interest in contributing. This document covers how to get set up,
what kinds of contributions are welcome, and the non-negotiable rules that keep the
bot safe and honest.

---

## Table of contents

1. [Safety-first policy](#safety-first-policy)
2. [What we welcome](#what-we-welcome)
3. [What we will not accept](#what-we-will-not-accept)
4. [Getting started](#getting-started)
5. [Running the tests](#running-the-tests)
6. [Code style](#code-style)
7. [Pull request workflow](#pull-request-workflow)
8. [Commit messages](#commit-messages)

---

## Safety-first policy

job-bot applies to real jobs on behalf of real people. A bug here has real-world
consequences — a rejected application, a legal exposure, or a privacy breach. Before
writing a single line of code, read and internalise these rules:

**The bot must never:**

- Auto-fill SSN, TIN, passport number, driver's licence, date of birth, or bank details.
  These fields always pause for human review, regardless of what a form label says.
- Fabricate or infer sensitive information. If a value is not explicitly present in the
  candidate's profile, the bot leaves the field empty or routes the application to the
  Review Queue — it does not guess.
- Bypass a CAPTCHA programmatically. The bot pauses and waits for the user.
- Answer bot-trap or honeypot fields ("If you are an AI, enter X...").
- Automatically answer non-standard criminal history questions (anything beyond the
  canonical "convicted of a felony" pattern).
- Apply to sites that require creating a company-specific account.
- Submit to the same job twice (deduplication must survive across sessions).
- Submit to listings that match any scam indicator (payment requests, WhatsApp-only
  contact, wildly unrealistic compensation, etc.).

These rules are enforced by `safety.py` and are tested exhaustively by the test suite.
**Any contribution that weakens, bypasses, or removes a safety invariant will be
rejected without exception, regardless of how useful the rest of the change is.**

If you believe a safety rule is wrong, open an issue to discuss it before writing code.

---

## What we welcome

| Area | Examples |
|------|---------|
| New ATS platforms | Support for a new Greenhouse variant, Lever subdomain pattern, Workday URL scheme, Rippling, Ashby, etc. |
| Safety improvements | More sensitive-field patterns, better scam-indicator heuristics, stronger deduplication |
| UI fixes and enhancements | Dashboard, History, Review Queue, Interview Tracker, or any React page |
| Resume scoring | Improvements to TF-IDF pipeline, new scoring signals, better keyword extraction |
| AI writer improvements | Better cover-letter prompts, ATS keyword extraction, token efficiency |
| Test coverage | New test cases in `tests/test_bot.py` for edge cases and regressions |
| Documentation | Clearer setup guides, troubleshooting tips, platform-specific notes |
| Performance | Faster discovery, smarter retries, better crash recovery |
| Accessibility | UI improvements for keyboard navigation, screen readers, colour contrast |

If you are unsure whether your idea fits, open an issue first — it saves everyone time.

---

## What we will not accept

- **Anything that bypasses, disables, or weakens a safety rule.** This includes
  "convenience" flags like `--skip-safety`, config options that unlock sensitive
  auto-fill, and code that changes a PAUSE classification to FILL.
- **Scraping login-walled sites.** The bot only operates on open-apply platforms.
  Do not add support for sites that require creating or logging into a company account
  (Taleo SSO portals, internal HR systems, etc.).
- **Spam or bulk-application shortcuts.** Changes designed to maximise volume at the
  expense of quality, deduplication integrity, or rate-limit compliance.
- **Credential storage shortcuts.** Passwords, tokens, or API keys must never appear
  in plaintext in any config file, log, CSV, screenshot, or commit. The existing
  Fernet-encryption flow in `api/security.py` must be used for any new secret.
- **PII in source code or tests.** No real names, email addresses, phone numbers,
  or resume content in test fixtures. Use obviously fake placeholders
  (`Jane Smith`, `jane@example.com`, `555-0100`, etc.).
- **Dependencies that introduce network calls to undocumented third parties.**
  The bot's external network surface is intentionally narrow (job boards + Claude API).

---

## Getting started

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/job-bot.git
cd job-bot

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Build the UI (requires Node 18+)
cd ui && npm install && npm run build && cd ..

# 5. Create a branch for your change
git checkout -b feat/my-new-feature
```

---

## Running the tests

```bash
python tests/test_bot.py
```

The test suite runs 96 checks covering every safety invariant: sensitive field
classification, scam detection, deduplication, salary guards, URL normalisation, EEO
handling, and a PII audit of all source files.

**All 96 tests must pass before you open a pull request.** If your change intentionally
alters a safety invariant (e.g., adding a new PAUSE field), you must also add a test
that proves the new behaviour.

Tests require no network access and no API keys — they run entirely against the local
codebase. They should complete in under 10 seconds.

---

## Code style

- **Python:** Follow [PEP 8](https://peps.python.org/pep-0008/). Maximum line length
  is 100 characters. Use type hints on all new function signatures.
- **React/TypeScript:** Match the style of the existing components in `ui/src/`.
  Run `npm run lint` inside `ui/` before committing frontend changes.
- **No unused imports.** Clean them up before opening a PR.
- **No commented-out code blocks.** Delete dead code rather than commenting it out.
- **Docstrings:** Public functions in `safety.py`, `form_filler.py`,
  `resume_selector.py`, and `api/` should have a one-line docstring explaining
  what the function does, not how.
- **Secrets and PII:** Never commit real API keys, profile files, resumes, CSVs, or
  screenshots. These paths are already in `.gitignore` — keep them there.

---

## Pull request workflow

1. Push your branch to your fork and open a pull request against `main`.
2. Fill in the pull request template completely. Incomplete templates will be asked
   to resubmit.
3. Ensure all tests pass (`python tests/test_bot.py`).
4. Keep PRs focused — one logical change per PR. If you have two unrelated fixes,
   open two PRs.
5. Respond to review comments within a reasonable time. PRs that go stale for more
   than 30 days may be closed.
6. Do not force-push to your branch after a review has started — add new commits
   instead, so the reviewer can see what changed.

---

## Commit messages

Use the conventional format:

```
<type>(<scope>): <short description>

[optional body — why, not what]
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `chore`

Examples:

```
feat(safety): add routing number to PAUSE field patterns
fix(form_filler): handle Workday multi-step salary page
test(safety): cover misdemeanor field edge cases
docs(readme): clarify --dry-run flag behaviour
```

The short description should be under 72 characters and written in the imperative
mood ("add", "fix", "handle" — not "added", "fixes", "handling").

---

## Questions?

Open a GitHub Discussion or a `question` issue. We are happy to help you scope a
contribution before you invest time writing code.
