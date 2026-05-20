"""
job_finder.py
Autonomous job discovery — two modes:

1. REVERSE RESUME DISCOVERY (--discover flag):
   Reads all resumes → extracts job titles + skills → builds search queries →
   scrapes LinkedIn/Google Jobs → scores each job against resumes → applies.

2. FIXED SEARCH URLS (fallback):
   Uses hardcoded LinkedIn search URLs if resume extraction finds nothing.
"""
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

try:
    from pypdf import PdfReader
    _PYPDF_OK = True
except ImportError:
    _PYPDF_OK = False

BASE_DIR = Path(__file__).parent

RESUME_FOLDER = {
    "muhammad": str(BASE_DIR / "resumes" / "muhammad"),
    "razia":    str(BASE_DIR / "resumes" / "razia"),
}

# Salary minimums per profile (0 = no filter)
SALARY_MIN = {
    "muhammad": 60_000,
    "razia":    110_000,
}

# Fallback LinkedIn searches if reverse-extraction produces nothing
_FALLBACK_SEARCHES = [
    "https://www.linkedin.com/jobs/search/?keywords=Systems+Administrator+OR+%22Microsoft+365%22+OR+Intune&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=IT+Support+Specialist+OR+%22IT+Infrastructure+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=Software+Engineer+OR+%22Data+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=Cloud+Engineer+OR+%22DevOps+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
]

# Known job-title patterns to scan resume text for
_TITLE_PATTERN = re.compile(
    r"\b("
    r"software engineer|systems administrator|it supervisor|"
    r"cybersecurity analyst|vulnerability management|endpoint security|"
    r"cloud engineer|devops engineer|it manager|data analyst|"
    r"it support specialist|network engineer|security engineer|"
    r"infrastructure engineer|platform engineer|backend developer|"
    r"full.?stack|ai engineer|ml engineer|product analyst|"
    r"identity engineer|iam engineer|data engineer|"
    r"project manager|solutions architect|site reliability"
    r")\b",
    re.I,
)

_SKILL_PATTERN = re.compile(
    r"\b("
    r"python|java|javascript|sql|azure|aws|intune|microsoft 365|"
    r"entra id|powershell|react|node\.?js|docker|kubernetes|"
    r"vulnerability|patch management|cloud|rest api|git|ci.?cd|"
    r"machine learning|llm|ai|automation|endpoint|mdm|siem|"
    r"golang|typescript|postgresql|mysql|terraform|ansible|"
    r"sharepoint|exchange|active directory|okta|sso|scim"
    r")\b",
    re.I,
)


# ── Step 1: Extract text from all resumes ─────────────────────────────────────

def _pdf_text(path: str) -> str:
    if not _PYPDF_OK:
        return ""
    try:
        reader = PdfReader(path)
        return " ".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _all_resume_text(profile: str) -> str:
    folder = Path(RESUME_FOLDER.get(profile, ""))
    if not folder.exists():
        return ""
    chunks = []
    for pdf in sorted(folder.glob("*.pdf")):
        chunks.append(_pdf_text(str(pdf)))
    return " ".join(chunks)


# ── Step 2: Extract job titles + skills from resume corpus ────────────────────

def extract_search_terms(profile: str) -> dict:
    """
    Read all resumes for profile, extract the most frequent job titles and
    top technical skills. Returns {"titles": [...], "skills": [...], "location": "New York"}.
    """
    text = _all_resume_text(profile)
    if not text:
        return {"titles": [], "skills": [], "location": "New York"}

    # Job titles (deduplicated, capped at 5)
    titles = list(dict.fromkeys(m.group(0).lower() for m in _TITLE_PATTERN.finditer(text)))[:5]

    # Top skills by frequency
    skills_raw = [m.group(0).lower() for m in _SKILL_PATTERN.finditer(text)]
    top_skills  = [s for s, _ in Counter(skills_raw).most_common(10)]

    print(f"  Titles found in resumes : {titles}")
    print(f"  Top skills              : {top_skills[:5]}")

    return {"titles": titles, "skills": top_skills, "location": "New York"}


# ── Step 3: Build search URLs from extracted terms ────────────────────────────

def build_search_queries(search_terms: dict) -> list[dict]:
    """Convert extracted titles/skills into LinkedIn and Google Jobs search URLs."""
    queries   = []
    location  = search_terms.get("location", "New York")
    titles    = search_terms.get("titles", [])
    skills    = search_terms.get("skills", [])[:5]

    if not titles:
        # Fallback to hardcoded searches
        for url in _FALLBACK_SEARCHES:
            queries.append({"platform": "linkedin", "url": url, "query": "fallback"})
        return queries

    for title in titles:
        enc_title = quote_plus(title)
        enc_loc   = quote_plus(location)

        # LinkedIn Easy Apply (f_AL=true)
        queries.append({
            "platform": "linkedin",
            "url":      f"https://www.linkedin.com/jobs/search/?keywords={enc_title}&location={enc_loc}&f_AL=true&sortBy=DD",
            "query":    title,
        })

        # Google Jobs
        queries.append({
            "platform": "google",
            "url":      f"https://www.google.com/search?q={enc_title}+jobs+{enc_loc}&udm=8",
            "query":    title,
        })

    return queries


# ── Step 4: Scrape job listings ───────────────────────────────────────────────

def _scrape_linkedin(page, url: str, existing: set, limit: int = 20) -> list[dict]:
    found = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        for _ in range(3):
            try:
                page.keyboard.press("End"); time.sleep(1)
            except Exception:
                break

        # Try multiple card selector patterns
        job_cards = []
        for sel in ["div.base-card", "li.jobs-search-results__list-item",
                    "div.job-card-container", "[data-job-id]"]:
            try:
                cards = page.locator(sel).all()
                if len(cards) >= 3:
                    job_cards = cards
                    break
            except Exception:
                pass

        for card in job_cards[:limit]:
            try:
                href = card.locator("a").first.get_attribute("href") or ""
                if "/jobs/view/" not in href:
                    continue
                url_clean = href.split("?")[0]
                if not url_clean.startswith("http"):
                    url_clean = "https://www.linkedin.com" + url_clean
                if url_clean in existing:
                    continue

                title   = _card_text(card, [".base-card__full-link", ".job-card-list__title", "h3"])
                company = _card_text(card, [".base-card__subtitle", ".job-card-container__company-name", "h4"])

                if title:
                    found.append({"url": url_clean, "title": title,
                                  "company": company, "notes": "LinkedIn auto-discovery"})
                    existing.add(url_clean)
            except Exception:
                pass
    except Exception as e:
        print(f"    LinkedIn error: {e}")
    return found


def _scrape_google_jobs(page, url: str, existing: set, limit: int = 10) -> list[dict]:
    """Extract job links from a Google Jobs search result page."""
    found = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Google Jobs links appear as anchor tags pointing to company sites
        for sel in ["a[href*='greenhouse.io']", "a[href*='lever.co']",
                    "a[href*='workday']", "a[href*='linkedin.com/jobs']"]:
            try:
                links = page.locator(sel).all()
                for link in links[:limit]:
                    href = link.get_attribute("href") or ""
                    if not href or href in existing:
                        continue
                    title = link.inner_text(timeout=500).strip()[:120]
                    if title:
                        found.append({"url": href, "title": title,
                                      "company": "", "notes": "Google Jobs discovery"})
                        existing.add(href)
            except Exception:
                pass
    except Exception as e:
        print(f"    Google Jobs error: {e}")
    return found


def _card_text(card, selectors: list) -> str:
    for sel in selectors:
        try:
            t = card.locator(sel).first.inner_text(timeout=500).strip()
            if t:
                return t
        except Exception:
            pass
    return ""


# ── Salary filter ─────────────────────────────────────────────────────────────

def _parse_max_salary(text: str):
    """Extract maximum salary number from a string like '$80-100K' or '$75,000'."""
    text = text.replace(",", "")
    m = re.search(r"\$?(\d+)\s*[kK]?\s*[-–]\s*\$?(\d+)\s*[kK]", text)
    if m:
        hi = int(m.group(2))
        return hi * 1000 if hi < 2000 else hi
    m = re.search(r"\$(\d+)\s*[kK]", text)
    if m:
        v = int(m.group(1))
        return v * 1000 if v < 2000 else v
    return None


def _salary_ok(notes: str, profile: str) -> bool:
    """Return True if job salary is above the profile minimum (or if salary unlisted)."""
    minimum = SALARY_MIN.get(profile, 0)
    if not minimum:
        return True
    max_sal = _parse_max_salary(notes or "")
    if max_sal is None:
        return True  # no salary listed — apply anyway
    return max_sal >= minimum


# ── Known-URL helpers ─────────────────────────────────────────────────────────

def _all_known_urls(profile_name: str) -> set:
    urls: set = set()
    jobs_csv = BASE_DIR / "jobs.csv"
    if jobs_csv.exists():
        try:
            urls.update(pd.read_csv(jobs_csv)["url"].dropna().astype(str))
        except Exception:
            pass
    for results_csv in (BASE_DIR / "output").glob("results_*.csv"):
        try:
            urls.update(pd.read_csv(results_csv)["url"].dropna().astype(str))
        except Exception:
            pass
    return urls


# ── Public API ────────────────────────────────────────────────────────────────

def discover_jobs(page, context, profile_name: str, applied_urls: set,
                  max_per_search: int = 20) -> list[dict]:
    """
    Full reverse-resume discovery:
      1. Extract titles/skills from all resumes
      2. Build search queries
      3. Scrape LinkedIn + Google Jobs
      4. Deduplicate and salary-filter
    Returns new job dicts ready to pass to process_job / append_to_jobs_csv.
    """
    existing = _all_known_urls(profile_name) | applied_urls
    found: list[dict] = []

    print(f"\n  Reading {profile_name}'s resumes to generate search queries...")
    search_terms = extract_search_terms(profile_name)
    queries      = build_search_queries(search_terms)
    print(f"  Generated {len(queries)} search queries")

    for q in queries:
        platform = q["platform"]
        url      = q["url"]
        print(f"  Searching [{platform}]: {q['query']} ...")

        if platform == "linkedin":
            batch = _scrape_linkedin(page, url, existing, max_per_search)
        else:
            batch = _scrape_google_jobs(page, url, existing, max_per_search)

        # Salary filter
        before = len(batch)
        batch  = [j for j in batch if _salary_ok(j.get("notes", ""), profile_name)]
        if before - len(batch):
            print(f"    Filtered {before - len(batch)} below-salary-minimum jobs")

        found.extend(batch)
        if batch:
            print(f"    + {len(batch)} new jobs")

    print(f"  Total new jobs found: {len(found)}")
    return found


def append_to_jobs_csv(new_jobs: list[dict]) -> list[dict]:
    """Append new jobs to jobs.csv with auto IDs. Returns actually-added rows."""
    jobs_csv = BASE_DIR / "jobs.csv"
    try:
        df            = pd.read_csv(jobs_csv)
        max_id        = int(df["id"].max()) if not df.empty else 0
        existing_urls = set(df["url"].dropna().astype(str))
    except Exception:
        max_id        = 0
        existing_urls = set()

    added = []
    for job in new_jobs:
        url = job.get("url", "")
        if not url or url in existing_urls:
            continue
        max_id += 1
        added.append({
            "id":       max_id,
            "url":      url,
            "company":  job.get("company", ""),
            "title":    job.get("title",   ""),
            "priority": "MED",
            "notes":    job.get("notes",   "auto-discovered"),
        })
        existing_urls.add(url)

    if added:
        pd.DataFrame(added).to_csv(
            jobs_csv, mode="a", header=False, index=False,
        )
        print(f"  Added {len(added)} new jobs to jobs.csv")

    return added
