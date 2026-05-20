"""
job_finder.py
Autonomous job discovery via LinkedIn and Google Jobs.
Returns new job dicts that aren't already in results CSV.
"""
import time
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent

# LinkedIn search URLs (Easy Apply filter = f_AL=true, sorted by date = sortBy=DD)
LINKEDIN_SEARCHES = [
    "https://www.linkedin.com/jobs/search/?keywords=Systems+Administrator+OR+%22Microsoft+365%22+OR+Intune&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=IT+Support+Specialist+OR+%22IT+Infrastructure+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=Software+Engineer+OR+%22Data+Engineer%22+OR+%22Backend+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
    "https://www.linkedin.com/jobs/search/?keywords=Cloud+Engineer+OR+%22DevOps+Engineer%22+OR+%22IAM+Engineer%22&location=New+York&f_AL=true&sortBy=DD",
]

# Google Jobs search queries → open each in browser and parse results
GOOGLE_SEARCHES = [
    "https://www.google.com/search?q=IT+Support+Specialist+jobs+New+York+site%3Agreenhouse.io+OR+site%3Alever.co",
    "https://www.google.com/search?q=Systems+Administrator+jobs+New+York+site%3Agreenhouse.io+OR+site%3Alever.co",
]


def discover_jobs(page, context, profile_name: str, applied_urls: set,
                  max_per_search: int = 20) -> list[dict]:
    """
    Search LinkedIn (and optionally Google) for new job postings.
    Returns list of dicts: {url, title, company, notes}.
    Skips any URL already in applied_urls or jobs.csv.
    """
    existing = _all_known_urls(profile_name) | applied_urls
    found: list[dict] = []

    print("\n  Searching LinkedIn for new jobs...")
    for search_url in LINKEDIN_SEARCHES:
        batch = _scrape_linkedin(page, context, search_url, existing, max_per_search)
        for job in batch:
            existing.add(job["url"])
            found.append(job)
        if batch:
            print(f"    + {len(batch)} jobs from: {search_url[50:90]}...")

    return found


def append_to_jobs_csv(new_jobs: list[dict]) -> list[dict]:
    """
    Append new jobs to jobs.csv with auto IDs.
    Returns only the rows that were actually new.
    """
    jobs_csv = BASE_DIR / "jobs.csv"
    try:
        df = pd.read_csv(jobs_csv)
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
            "title":    job.get("title", ""),
            "priority": "MED",
            "notes":    job.get("notes", "auto-discovered"),
        })
        existing_urls.add(url)

    if added:
        new_df = pd.DataFrame(added)
        with open(jobs_csv, "a", newline="") as f:
            new_df.to_csv(f, header=False, index=False)
        print(f"  Added {len(added)} new jobs to jobs.csv")

    return added


# ── Internal ──────────────────────────────────────────────────────────────────

def _all_known_urls(profile_name: str) -> set:
    """Collect all URLs from jobs.csv and results CSVs."""
    urls: set[str] = set()
    jobs_csv = BASE_DIR / "jobs.csv"
    if jobs_csv.exists():
        try:
            df = pd.read_csv(jobs_csv)
            urls.update(df["url"].dropna().astype(str))
        except Exception:
            pass
    for results_csv in (BASE_DIR / "output").glob("results_*.csv"):
        try:
            df = pd.read_csv(results_csv)
            urls.update(df["url"].dropna().astype(str))
        except Exception:
            pass
    return urls


def _scrape_linkedin(page, context, search_url: str,
                     existing_urls: set, limit: int) -> list[dict]:
    """Navigate to a LinkedIn job search page and extract job listings."""
    found = []
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Scroll to load more cards
        for _ in range(3):
            try:
                page.keyboard.press("End")
                time.sleep(1)
            except Exception:
                break

        # Try multiple card selectors (LinkedIn A/B tests layouts)
        job_cards = []
        for sel in [
            "div.base-card",
            "li.jobs-search-results__list-item",
            "div.job-card-container",
            "[data-job-id]",
        ]:
            try:
                cards = page.locator(sel).all()
                if len(cards) >= 3:
                    job_cards = cards
                    break
            except Exception:
                pass

        for card in job_cards[:limit]:
            try:
                # URL
                link = card.locator("a").first
                href = link.get_attribute("href") or ""
                if not href:
                    continue
                url = href.split("?")[0]
                if "/jobs/view/" not in url:
                    continue
                if not url.startswith("http"):
                    url = "https://www.linkedin.com" + url
                if url in existing_urls:
                    continue

                # Title
                title = ""
                for title_sel in [
                    ".base-card__full-link",
                    ".job-card-list__title",
                    "h3",
                    ".job-card-container__link",
                ]:
                    try:
                        el = card.locator(title_sel).first
                        t  = el.inner_text(timeout=500).strip()
                        if t:
                            title = t
                            break
                    except Exception:
                        pass

                # Company
                company = ""
                for comp_sel in [
                    ".base-card__subtitle",
                    ".job-card-container__company-name",
                    "h4",
                    ".job-card-container__primary-description",
                ]:
                    try:
                        el = card.locator(comp_sel).first
                        c  = el.inner_text(timeout=500).strip()
                        if c:
                            company = c
                            break
                    except Exception:
                        pass

                if title:
                    found.append({
                        "url":     url,
                        "title":   title,
                        "company": company,
                        "notes":   "LinkedIn auto-discovery",
                    })
                    existing_urls.add(url)

            except Exception:
                pass

    except Exception as e:
        print(f"    LinkedIn search error: {e}")

    return found
