"""
job_finder.py
Autonomous job discovery — two modes:

1. REVERSE RESUME DISCOVERY (--discover flag):
   Reads all resumes → extracts job titles + skills → builds search queries →
   scrapes LinkedIn/Google Jobs → scores each job against resumes → applies.

2. FIXED SEARCH URLS (fallback):
   Uses hardcoded LinkedIn search URLs if resume extraction finds nothing.
"""
import random
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus, urlparse

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

# Open-apply ATS platforms — no company-specific account required to submit an application.
# Discovery only queues jobs whose apply URL is hosted on one of these domains.
_OPEN_ATS_DOMAINS = {
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "workday.com",
    "ashbyhq.com",
    "smartrecruiters.com",
    "icims.com",
    "taleo.net",
    "brassring.com",
    "jobvite.com",
    "bamboohr.com",
    "breezy.hr",
    "recruitee.com",
    "workable.com",
    "applytojob.com",
    "paylocity.com",
    "indeed.com",
    "linkedin.com",
}


def _is_open_ats_url(url: str) -> bool:
    """Return True if URL is hosted on a known open-apply ATS (no company login needed)."""
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _OPEN_ATS_DOMAINS)
    except Exception:
        return False


# Tier 1 — direct Greenhouse / Lever / Workday job board URLs for target companies.
# These are open-apply platforms: no company-specific account required.
PRIORITY_COMPANIES = {
    "muhammad": [
        {"name": "Spotify",    "url": "https://boards.greenhouse.io/spotify"},
        {"name": "Cloudflare", "url": "https://boards.greenhouse.io/cloudflare"},
        {"name": "Datadog",    "url": "https://boards.greenhouse.io/datadog"},
        {"name": "MongoDB",    "url": "https://boards.greenhouse.io/mongodb"},
        {"name": "Twilio",     "url": "https://boards.greenhouse.io/twilio"},
        {"name": "Squarespace","url": "https://boards.greenhouse.io/squarespace"},
        {"name": "Etsy",       "url": "https://boards.greenhouse.io/etsy"},
        {"name": "Stripe",     "url": "https://jobs.lever.co/stripe"},
        {"name": "Figma",      "url": "https://boards.greenhouse.io/figma"},
        {"name": "Two Sigma",  "url": "https://boards.greenhouse.io/twosigma"},
        {"name": "Palantir",   "url": "https://jobs.lever.co/palantir"},
        {"name": "Okta",       "url": "https://boards.greenhouse.io/okta"},
    ],
    "razia": [
        {"name": "Snyk",            "url": "https://boards.greenhouse.io/snyk"},
        {"name": "Wiz",             "url": "https://boards.greenhouse.io/wizsecurity"},
        {"name": "Recorded Future", "url": "https://boards.greenhouse.io/recordedfuture"},
        {"name": "Arctic Wolf",     "url": "https://boards.greenhouse.io/arcticwolf"},
        {"name": "Abnormal",        "url": "https://boards.greenhouse.io/abnormalsecurity"},
        {"name": "Huntress",        "url": "https://boards.greenhouse.io/huntresslabs"},
        {"name": "Tenable",         "url": "https://boards.greenhouse.io/tenable"},
        {"name": "CrowdStrike",     "url": "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers"},
        {"name": "Palo Alto",       "url": "https://paloaltonetworks.wd3.myworkdayjobs.com/en-US/External"},
        {"name": "Rapid7",          "url": "https://boards.greenhouse.io/rapid7"},
        {"name": "Lacework",        "url": "https://boards.greenhouse.io/lacework"},
        {"name": "Cybereason",      "url": "https://boards.greenhouse.io/cybereason"},
    ],
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
    """Extract job links from a Google Jobs search result page — only open-ATS URLs."""
    found = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Build selectors from the open ATS domain list
        ats_selectors = [
            f"a[href*='{d}']" for d in [
                "greenhouse.io", "lever.co", "myworkdayjobs.com",
                "ashbyhq.com", "smartrecruiters.com", "icims.com",
                "jobvite.com", "bamboohr.com", "workable.com",
                "linkedin.com/jobs", "indeed.com/viewjob",
            ]
        ]
        for sel in ats_selectors:
            try:
                links = page.locator(sel).all()
                for link in links[:limit]:
                    href = link.get_attribute("href") or ""
                    if not href or href in existing:
                        continue
                    if not _is_open_ats_url(href):
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


# ── Tier 1: Company career page scraper ───────────────────────────────────────

_CAREER_ERROR_PHRASES = [
    "this site can't be reached", "dns_probe_finished", "err_name_not_resolved",
    "err_connection_refused", "page not found", "404 not found", "404 error",
    "the page you requested was not found", "sorry, we couldn't find",
    "no page found", "page doesn't exist",
]

_CAREER_AUTH_PHRASES = [
    "sign in to apply", "log in to apply", "create account to apply",
    "create an account to continue", "please sign in or register",
    "register to apply", "sign up to apply", "login required",
    "you must be logged in", "please log in to continue",
]


def _scrape_company_careers(page, company: dict, search_terms: dict,
                             existing: set, limit: int = 15) -> list:
    """Best-effort scraper for a company career page. Returns [] on any error."""
    found   = []
    name    = company["name"]
    titles  = search_terms.get("titles", [])
    query   = quote_plus(" ".join(titles[:2]) if titles else "IT systems administrator")
    raw_url = company["url"].format(query=query)

    try:
        page.goto(raw_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)

        # Fast-fail: DNS errors, 404s, auth walls
        try:
            body_low = page.inner_text("body").lower()[:1500]
            if any(p in body_low for p in _CAREER_ERROR_PHRASES):
                print(f"    {name}: page unavailable — skipping")
                return []
            if any(p in body_low for p in _CAREER_AUTH_PHRASES):
                print(f"    {name}: requires login to view jobs — skipping")
                return []
        except Exception:
            pass

        # Broad link selectors that work across different ATS platforms
        for sel in [
            "a[href*='/jobs/view/']", "a[href*='/job/']", "a[href*='/jobs/']",
            "a[href*='/careers/']", "a[href*='/openings/']", "a[href*='/position']",
            "[class*='job-card'] a", "[class*='job-listing'] a", "[class*='job-item'] a",
            "[class*='position-card'] a", "[class*='result-card'] a",
            "li.lv-job-result a", ".job-list-item a", "[data-job-id] a",
            "h2 a", "h3 a",
        ]:
            try:
                links = page.locator(sel).all()
                if not links:
                    continue
                for link in links[:limit]:
                    try:
                        href = link.get_attribute("href") or ""
                        if not href:
                            continue
                        if href.startswith("/"):
                            base = urlparse(raw_url)
                            href = f"{base.scheme}://{base.netloc}{href}"
                        elif not href.startswith("http"):
                            continue
                        if href in existing:
                            continue
                        text = link.inner_text(timeout=500).strip()[:120]
                        if not text or len(text) < 4 or len(text) > 150:
                            continue
                        found.append({
                            "url": href, "title": text, "company": name,
                            "notes": f"Tier 1 — {name}",
                            "source_tier": 1, "source": "direct_company",
                        })
                        existing.add(href)
                    except Exception:
                        pass
                if len(found) >= 3:
                    break
            except Exception:
                pass
    except Exception as e:
        print(f"    Career page error ({name}): {e}")

    # Only keep URLs on open-apply ATS platforms
    before = len(found)
    found = [j for j in found if _is_open_ats_url(j["url"])]
    if before and not found:
        print(f"      (no open-ATS links found on {name} — skipping)")
    return found


# ── Tier 2: Indeed scraper ────────────────────────────────────────────────────

def _scrape_indeed(page, search_terms: dict, existing: set, limit: int = 20) -> list:
    """Scrape Indeed full-time job listings for extracted search terms."""
    found  = []
    titles = search_terms.get("titles", [])
    loc    = search_terms.get("location", "New York")
    if not titles:
        titles = ["IT support specialist"]

    for title in titles[:3]:
        query   = quote_plus(title)
        enc_loc = quote_plus(loc)
        url = (
            f"https://www.indeed.com/jobs?q={query}&l={enc_loc}"
            f"&sc=0kf%3Ajt%28fulltime%29%3B&sort=date"
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            for _ in range(2):
                try:
                    page.keyboard.press("End")
                    time.sleep(1)
                except Exception:
                    break

            for sel in [
                "a.jcs-JobTitle", "h2.jobTitle a", "[data-jk] h2 a",
                "a[href*='/viewjob']", ".job_seen_beacon a",
                "[class*='JobTitle'] a", "a[id^='job_']",
            ]:
                try:
                    cards = page.locator(sel).all()
                    for card in cards[:limit]:
                        href = card.get_attribute("href") or ""
                        if not href:
                            continue
                        if not href.startswith("http"):
                            href = "https://www.indeed.com" + href
                        # Normalise to jk param
                        parsed = urlparse(href)
                        from urllib.parse import parse_qs as _pqs
                        jk = _pqs(parsed.query).get("jk", [""])[0]
                        clean = f"https://www.indeed.com/viewjob?jk={jk}" if jk else href
                        if clean in existing or not jk:
                            continue
                        text = card.inner_text(timeout=500).strip()[:120]
                        if text:
                            found.append({
                                "url": clean, "title": text, "company": "",
                                "notes": f"Indeed: {title}",
                                "source_tier": 2, "source": "indeed",
                            })
                            existing.add(clean)
                    if found:
                        break
                except Exception:
                    pass
        except Exception as e:
            print(f"    Indeed error: {e}")

    return found


# ── Cross-platform deduplication by (company, title) ─────────────────────────

def _deduplicate_by_title_company(jobs: list) -> list:
    """
    Remove cross-platform duplicates by normalised (company, title) pairs.
    When duplicates exist, keep the version from the lowest (best) tier.
    """
    seen: dict = {}
    for job in jobs:
        co  = re.sub(r"[^a-z0-9]", "", (job.get("company") or "").lower())
        ti  = re.sub(r"[^a-z0-9]", "", (job.get("title")   or "").lower())[:40]
        key = (co, ti)
        if not co and not ti:
            seen[job.get("url", id(job))] = job
            continue
        tier = job.get("source_tier", 9)
        if key not in seen or tier < seen[key].get("source_tier", 9):
            seen[key] = job

    deduped = list(seen.values())
    deduped.sort(key=lambda j: j.get("source_tier", 9))
    return deduped


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
    # results CSV uses "job_url" column (not "url") — try both for safety
    for results_csv in (BASE_DIR / "output").glob("results_*.csv"):
        try:
            df = pd.read_csv(results_csv)
            col = "job_url" if "job_url" in df.columns else "url"
            urls.update(df[col].dropna().astype(str))
        except Exception:
            pass
    return urls


# ── Public API ────────────────────────────────────────────────────────────────

def discover_jobs(page, context, profile_name: str, applied_urls: set,
                  max_per_search: int = 20,
                  tier_max: int = 3,
                  companies_only: bool = False):
    """
    Tiered job discovery (all sources require no company-specific login):
      Tier 1 — Indeed
      Tier 2 — LinkedIn Easy Apply
      Tier 3 — Google Jobs (open-ATS links only)
      Tier 4 — Direct Greenhouse / Lever / Workday company boards

    Returns new job dicts with source_tier + source fields, deduped cross-platform.
    """
    existing  = _all_known_urls(profile_name) | applied_urls
    all_jobs  = []

    print(f"\n  Reading {profile_name}'s resumes to generate search queries...")
    search_terms = extract_search_terms(profile_name)

    # Build search queries once — used by Tier 2 (LinkedIn) and Tier 3 (Google)
    queries: list = []

    # ── Tier 1: Indeed ────────────────────────────────────────────────────────
    if tier_max >= 1 and not companies_only:
        print(f"\n  [Tier 1] Searching Indeed...")
        batch = _scrape_indeed(page, search_terms, existing, max_per_search)
        for j in batch:
            j.setdefault("source_tier", 1)
            j.setdefault("source", "indeed")
        all_jobs.extend(batch)
        print(f"    + {len(batch)} found")

    # ── Tier 2: LinkedIn Easy Apply ───────────────────────────────────────────
    if tier_max >= 2 and not companies_only:
        queries = build_search_queries(search_terms)
        li_queries = [q for q in queries if q["platform"] == "linkedin"]
        print(f"\n  [Tier 2] Searching LinkedIn ({len(li_queries)} queries)...")
        for q in li_queries:
            print(f"    {q['query']} ...")
            batch = _scrape_linkedin(page, q["url"], existing, max_per_search)
            for j in batch:
                j["source_tier"] = 2
                j["source"]      = "linkedin"
            all_jobs.extend(batch)
            if batch:
                print(f"      + {len(batch)} found")

    # ── Tier 3: Google Jobs (open-ATS links only) ─────────────────────────────
    if tier_max >= 3 and not companies_only:
        if not queries:
            queries = build_search_queries(search_terms)
        goog_queries = [q for q in queries if q["platform"] == "google"]
        print(f"\n  [Tier 3] Searching Google Jobs ({len(goog_queries)} queries)...")
        for q in goog_queries:
            print(f"    {q['query']} ...")
            batch = _scrape_google_jobs(page, q["url"], existing, max_per_search)
            for j in batch:
                j["source_tier"] = 3
                j["source"]      = "google_jobs"
            all_jobs.extend(batch)
            if batch:
                print(f"      + {len(batch)} found")

    # ── Tier 4: Direct ATS company boards (Greenhouse / Lever / Workday) ──────
    if tier_max >= 4 or companies_only:
        companies = PRIORITY_COMPANIES.get(profile_name, [])
        print(f"\n  [Tier 4] Searching {len(companies)} ATS company boards...")
        for company in companies:
            print(f"    {company['name']} ...")
            batch = _scrape_company_careers(page, company, search_terms,
                                            existing, max_per_search)
            all_jobs.extend(batch)
            if batch:
                print(f"      + {len(batch)} found")
            time.sleep(random.uniform(1.0, 2.0))

    # ── Dedup cross-platform ──────────────────────────────────────────────────
    deduped = _deduplicate_by_title_company(all_jobs)
    removed = len(all_jobs) - len(deduped)
    print(f"\n  Total found: {len(all_jobs)} → after dedup: {len(deduped)} "
          f"({removed} cross-platform dupes removed)")
    return deduped


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
            "id":         max_id,
            "url":        url,
            "company":    job.get("company", ""),
            "title":      job.get("title",   ""),
            "priority":   "MED",
            "notes":      job.get("notes",   "auto-discovered"),
            "source_tier": job.get("source_tier", 0),
            "source":     job.get("source", "discovery"),
        })
        existing_urls.add(url)

    if added:
        pd.DataFrame(added).to_csv(
            jobs_csv, mode="a", header=False, index=False,
        )
        print(f"  Added {len(added)} new jobs to jobs.csv")

    return added
