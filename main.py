#!/usr/bin/env python3
"""
main.py — Job Application Bot

Usage:
  python main.py --profile muhammad
  python main.py --profile muhammad --discover
  python main.py --profile muhammad --discover --review
  python main.py --profile muhammad --discover --limit 25
  python main.py --profile muhammad --discover --dry-run
  python main.py --profile razia --discover
  python main.py --profile razia --discover --review

Flags:
  --profile    : muhammad or razia
  --discover   : auto-find new jobs from resume text before applying
  --review     : show each job, ask y/n/q before submitting
  --limit N    : max jobs per session (default: 50)
  --dry-run    : score + log everything, never actually submit
  --min-score  : skip if score < this AND fit label is Low Fit (default: 0.0 = off)
                 set above 0 to enable (e.g. 0.05)
"""
import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import pandas as pd
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from form_filler import (
    click_submit, detect_platform, detect_recaptcha, dismiss_popups,
    extract_job_description, fill_form, fill_indeed_easy_apply,
    find_submit_button, handle_linkedin_apply, parse_max_salary,
    wait_for_submission_confirmation,
)
from job_finder import append_to_jobs_csv, discover_jobs
from resume_selector import fit_label, pick_resume_with_details, verify_resumes

console = Console()

BASE_DIR     = Path(__file__).parent
OUTPUT_DIR   = BASE_DIR / "output"
BROWSER_PROF = BASE_DIR / "browser_profile"
MAX_JOB_SECS = 180  # 3 min — covers multi-step Workday/LinkedIn forms with CAPTCHA pauses

# URL params stripped for deduplication
_STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "from", "ref", "src", "tracking", "gh_src", "trk",
    "currentJobId", "tk", "hl", "refId", "trackingId",
}


# ── URL normalization ─────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Strip tracking params and trailing slash for deduplication."""
    try:
        p      = urlparse(url)
        params = {k: v for k, v in parse_qs(p.query).items()
                  if k.lower() not in _STRIP_PARAMS}
        clean  = urlunparse(p._replace(query=urlencode(params, doseq=True)))
        return clean.rstrip("/")
    except Exception:
        return url.rstrip("/")


# ── Session stats ─────────────────────────────────────────────────────────────

class SessionStats:
    def __init__(self):
        self.discovered      = 0
        self.duplicates      = 0
        self.scored          = 0
        self.attempted       = 0
        self.submitted       = 0
        self.submit_failed   = 0
        self.captcha         = 0
        self.errors          = 0
        self.dry_run         = 0
        self.resume_replaced = 0
        self.by_fit: dict    = {k: 0 for k in
                                ("Strong Fit", "Good Fit", "Possible Fit", "Stretch", "Low Fit")}
        self.by_tier: dict   = {1: 0, 2: 0, 3: 0, 4: 0, 0: 0}
        self.by_apply_method: dict = {
            "direct_form": 0, "easy_apply": 0,
            "company_site_redirect": 0, "simple_apply": 0,
        }
        self.top_jobs: list = []

    def record(self, company: str, title: str, score: float,
               fit: str, status: str, source_tier: int = 0,
               apply_method: str = "", resume_replaced: bool = False):
        self.scored += 1
        self.by_fit[fit] = self.by_fit.get(fit, 0) + 1
        self.by_tier[source_tier] = self.by_tier.get(source_tier, 0) + 1
        if apply_method in self.by_apply_method:
            self.by_apply_method[apply_method] += 1
        if resume_replaced:
            self.resume_replaced += 1
        if status in ("submitted", "submitted_manually"):
            self.submitted += 1
        elif status == "submit_failed":
            self.submit_failed += 1
        elif status == "error":
            self.errors += 1
        elif status == "dry_run":
            self.dry_run += 1
        elif status not in ("skipped_manual", "already_applied", "watchdog_timeout"):
            self.attempted += 1
        self.top_jobs.append((company, title, score, fit, apply_method or ""))
        self.top_jobs.sort(key=lambda x: x[2], reverse=True)
        self.top_jobs = self.top_jobs[:10]

    def print_summary(self):
        console.rule("[bold]Run Summary[/bold]")

        tier_names = {
            1: "Direct company pages", 2: "Indeed",
            3: "LinkedIn", 4: "Google Jobs", 0: "CSV/manual",
        }
        console.print("\n  Jobs discovered by tier:")
        for tier in sorted(self.by_tier):
            count = self.by_tier[tier]
            if count:
                console.print(f"    {tier_names.get(tier, f'Tier {tier}')}: {count}")

        console.print(f"\n  Duplicates skipped (already applied): {self.duplicates}")
        console.print(f"  Jobs scored: {self.scored}")

        console.print("\n  Applications attempted:")
        console.print(f"    Total: {self.attempted}")
        for method, count in self.by_apply_method.items():
            if count:
                console.print(f"    {method}: {count}")

        console.print(f"\n  [green]Submitted: {self.submitted}[/green]")
        console.print(f"    Resume replaced successfully: {self.resume_replaced}")
        used_default = max(0, self.submitted - self.resume_replaced)
        console.print(f"    Used account default resume: {used_default}")
        console.print(f"  Submit failed: {self.submit_failed}")
        console.print(f"  Manual CAPTCHA solved: {self.captcha}")
        console.print(f"  Errors: {self.errors}")
        console.print(f"  Dry run (not submitted): {self.dry_run}")

        console.print("\n  By fit label:")
        for lbl, count in self.by_fit.items():
            if count:
                console.print(f"    {lbl}: {count}")

        if self.top_jobs:
            console.print("\n  Top 10 by resume score:")
            for i, (co, ti, sc, fl, meth) in enumerate(self.top_jobs, 1):
                suffix = f", {meth}" if meth else ""
                console.print(f"    {i:2}. {co} — {ti} (score: {sc:.2f}, {fl}{suffix})")


# ── Watchdog ──────────────────────────────────────────────────────────────────

class Watchdog:
    def __init__(self, timeout_s: float = MAX_JOB_SECS):
        self._last  = time.time()
        self._limit = timeout_s

    def ping(self):
        self._last = time.time()

    @property
    def timed_out(self) -> bool:
        return (time.time() - self._last) > self._limit

    def elapsed(self) -> float:
        return time.time() - self._last


# ── Status printing ───────────────────────────────────────────────────────────

_STATUS_STYLES = {
    "SUBMITTED":       "[bold green]",
    "SKIPPED":         "[yellow]",
    "STUCK":           "[bold red]",
    "ERROR":           "[red]",
    "ALREADY_APPLIED": "[dim]",
    "SUBMIT_FAILED":   "[bold red]",
    "DRY_RUN":         "[cyan]",
    "MANUAL_NEEDED":   "[bold yellow]",
}

def print_status(tag: str, detail: str = ""):
    style  = _STATUS_STYLES.get(tag, "[white]")
    close  = style.replace("[", "[/")
    suffix = f"  {detail}" if detail else ""
    console.print(f"  {style}[{tag}]{close}{suffix}")


# ── Salary parsing (logging only) ─────────────────────────────────────────────

_SALARY_TARGET = {"muhammad": 75_000, "razia": 110_000}

def parse_salary_label(text: str, profile_name: str) -> tuple[str, str]:
    """
    Returns (parsed_salary_str, label) where label is
    above_target / at_target / below_target / not_listed.
    """
    text = (text or "").replace(",", "")
    # Hourly detection
    hourly_m = re.search(r"\$(\d+\.?\d*)\s*[-–/]?\s*\$?(\d+\.?\d*)?\s*/?\s*hr", text, re.I)
    if hourly_m:
        hi = float(hourly_m.group(2) or hourly_m.group(1))
        annual = int(hi * 2080)
    else:
        annual = parse_max_salary(text) or 0

    if not annual:
        return "not_listed", "not_listed"

    target = _SALARY_TARGET.get(profile_name, 75_000)
    label  = ("above_target" if annual > target * 1.05
              else "at_target" if annual >= target * 0.95
              else "below_target")
    return f"${annual:,}", label


# ── Profile loading ───────────────────────────────────────────────────────────

def load_profile(name: str) -> dict:
    for path in [BASE_DIR / "config" / f"{name}_profile.json",
                 BASE_DIR / name / f"{name}_profile.json"]:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if "phone_formatted" not in data and "phone" in data:
                p = data["phone"]
                data["phone_formatted"] = (
                    f"({p[:3]}) {p[3:6]}-{p[6:]}" if len(p) == 10 and p.isdigit() else p
                )
            return data
    console.print(f"[red]Profile not found: {name}[/red]")
    sys.exit(1)


# ── Deduplication ─────────────────────────────────────────────────────────────

def load_applied_urls(profile_name: str) -> set:
    results_csv = OUTPUT_DIR / f"results_{profile_name}.csv"
    applied: set = set()
    if not results_csv.exists():
        return applied
    try:
        with open(results_csv, newline="") as f:
            for row in csv.DictReader(f):
                status = row.get("status", "").lower()
                url    = normalize_url(row.get("job_url", row.get("url", "")).strip())
                if url and status not in ("error",):
                    applied.add(url)
    except Exception:
        pass
    return applied


# ── Logging ───────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "timestamp", "profile", "company", "title", "location", "salary_parsed",
    "salary_label", "job_url", "final_url", "source_tier", "source",
    "platform", "ats_platform", "apply_method",
    "selected_resume", "resume_score", "fit_label", "matched_keywords",
    "resume_replaced", "resume_replacement_method",
    "cover_letter_used", "status", "screenshot_path", "error_notes",
]

def log_result(profile_name: str, entry: dict):
    """Write to both results_{profile}.csv and results_{profile}.jsonl."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entry.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
    entry.setdefault("profile",   profile_name)

    # CSV
    csv_path = OUTPUT_DIR / f"results_{profile_name}.csv"
    exists   = csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(entry)

    # JSONL
    jsonl_path = OUTPUT_DIR / f"results_{profile_name}.jsonl"
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _make_entry(profile_name: str, row: dict, status: str,
                pdf_path: str, score: float, fit: str,
                keywords: list, screenshot: str = "",
                notes: str = "", salary_text: str = "",
                field_log: list = None, apply_method: str = "",
                final_url: str = "") -> dict:
    sal_parsed, sal_label = parse_salary_label(
        salary_text or row.get("notes", ""), profile_name
    )
    # Extract resume replacement metadata from field_log sentinel entries
    resume_replaced = "no"
    resume_replacement_method = ""
    if field_log:
        for entry in field_log:
            if entry.get("field") == "_meta_resume_replaced":
                resume_replaced = entry.get("status", "no")
                resume_replacement_method = entry.get("value", "")
                break
    return {
        "timestamp":                 datetime.now().strftime("%Y-%m-%d %H:%M"),
        "profile":                   profile_name,
        "company":                   row.get("company", ""),
        "title":                     row.get("title", ""),
        "location":                  row.get("location", ""),
        "salary_parsed":             sal_parsed,
        "salary_label":              sal_label,
        "job_url":                   row.get("url", ""),
        "final_url":                 final_url or row.get("url", ""),
        "source_tier":               row.get("source_tier", 0),
        "source":                    row.get("source", "csv"),
        "platform":                  row.get("platform", ""),
        "ats_platform":              row.get("platform", ""),
        "apply_method":              apply_method,
        "selected_resume":           Path(pdf_path).name if pdf_path else "",
        "resume_score":              f"{score:.3f}",
        "fit_label":                 fit,
        "matched_keywords":          ", ".join(keywords),
        "resume_replaced":           resume_replaced,
        "resume_replacement_method": resume_replacement_method,
        "cover_letter_used":         "yes" if keywords else "no",
        "status":                    status,
        "screenshot_path":           screenshot,
        "error_notes":               notes,
    }


# ── Screenshot helper ─────────────────────────────────────────────────────────

def take_screenshot(page, company: str, title: str, suffix: str) -> str:
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe  = re.sub(r"[^\w]+", "_", f"{company}_{title}")[:60]
    fname = f"{ts}_{safe}_{suffix}.png"
    screenshots_dir = OUTPUT_DIR / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    path  = str(screenshots_dir / fname)
    try:
        page.screenshot(path=path, timeout=60000, animations="disabled")
        console.print(f"  Screenshot: {fname}")
    except Exception as e:
        console.print(f"  [yellow]Screenshot skipped: {e}[/yellow]")
        return ""
    return path


# ── Field log summary ─────────────────────────────────────────────────────────

def print_field_summary(field_log: list):
    filled  = [x for x in field_log if x["status"] == "filled"]
    skipped = [x for x in field_log if x["status"] == "skipped"]
    errors  = [x for x in field_log if x["status"] == "error"]
    console.print(f"\n  Fields filled ({len(filled)}):", style="green")
    for x in filled:
        console.print(f"    • {x['field']}: {x.get('value','')[:80]}")
    if skipped:
        console.print(f"  Skipped ({len(skipped)}):", style="yellow")
    if errors:
        console.print(f"  Errors ({len(errors)}):", style="red")
        for x in errors:
            console.print(f"    • {x['field']} — {x.get('note','')}")


# ── Startup verification ──────────────────────────────────────────────────────

def print_startup_verification(profile_name: str):
    found, total, missing = verify_resumes(profile_name)
    if missing:
        console.print(f"  Resumes: [yellow]{found}/{total}[/yellow] "
                      f"([red]{len(missing)} missing[/red])")
        for m in missing[:5]:
            console.print(f"    [red]✗[/red] {m}")
        if len(missing) > 5:
            console.print(f"    ... and {len(missing)-5} more")
    else:
        console.print(f"  Resumes: [green]{found}/{total} all found[/green]")


# ── Core job processor ────────────────────────────────────────────────────────

def process_job(page, context, row: dict, row_num: int,
                profile: dict, profile_name: str,
                applied_urls: set, stats: SessionStats,
                dry_run: bool = False, review: bool = False,
                min_score: float = 0.05) -> str:
    """
    Returns "continue" | "stop".
    Applies to EVERY job — never skips based on salary, seniority, or score
    (except score < min_score AND Low Fit, which is opt-in).
    """
    url     = str(row.get("url", "")).strip()
    company = str(row.get("company", "Unknown")).strip()
    title   = str(row.get("title",   "Unknown")).strip()
    notes   = str(row.get("notes",   ""))
    norm_url = normalize_url(url)

    console.rule(f"[bold blue]Job {row_num}: {company} — {title}[/bold blue]")
    console.print(f"  URL: {url}")

    watchdog = Watchdog(MAX_JOB_SECS)

    # ── 1. Deduplication ─────────────────────────────────────────────────────
    if norm_url in applied_urls:
        print_status("ALREADY_APPLIED")
        stats.duplicates += 1
        return "continue"

    # ── 2. Navigate ──────────────────────────────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(1.0, 2.0))
        try:
            dismiss_popups(page)
        except Exception:
            pass
        watchdog.ping()
    except Exception as e:
        print_status("ERROR", f"navigation: {e}")
        log_result(profile_name, _make_entry(
            profile_name, row, "error", "", 0.0, "Low Fit", [], notes=f"nav: {e}"))
        stats.errors += 1
        return "continue"

    platform = detect_platform(page.url)
    row["platform"] = platform
    console.print(f"  Platform: [cyan]{platform}[/cyan]")

    # ── 3. Extract JD ────────────────────────────────────────────────────────
    # Check if page is 404 or closed — only hard skip
    try:
        body_low = page.inner_text("body").lower()[:500]
        if any(kw in body_low for kw in ["page not found", "job is no longer",
                                          "position has been filled",
                                          "this job is closed", "404"]):
            print_status("SKIPPED", "posting closed/404")
            log_result(profile_name, _make_entry(
                profile_name, row, "closed", "", 0.0, "Low Fit", [], notes="posting closed"))
            applied_urls.add(norm_url)
            return "continue"
    except Exception:
        pass

    # ── 4. Indeed handling ───────────────────────────────────────────────────
    active_page = page
    pdf_path    = ""
    jd_text     = ""

    if platform == "indeed":
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        watchdog.ping()

        if "indeed.com" not in page.url:
            platform = detect_platform(page.url)
            row["platform"] = platform
            console.print(f"  Redirected: [cyan]{platform}[/cyan]")
        else:
            jd_text   = extract_job_description(page, "indeed")
            pdf_path, score, fit, keywords, fname = pick_resume_with_details(
                title, notes, profile_name, company, jd_text,
            )
            _print_resume_selection(title, company, fname, score, fit, keywords)

            # Score gate (only if enabled and Low Fit)
            if min_score > 0 and score < min_score and fit == "Low Fit":
                print_status("SKIPPED", f"score {score:.3f} < {min_score} (Low Fit)")
                log_result(profile_name, _make_entry(
                    profile_name, row, "skipped_low_fit", pdf_path,
                    score, fit, keywords, notes=f"score {score:.3f}"))
                applied_urls.add(norm_url)
                return "continue"

            indeed_log: list = []
            mode = fill_indeed_easy_apply(
                page, context, profile, profile_name, pdf_path,
                indeed_log, company, title,
            )
            watchdog.ping()
            console.print(f"  Indeed mode: [cyan]{mode}[/cyan]")

            if mode == "company_site":
                active_page = context.pages[-1]
                platform    = detect_platform(active_page.url)
                row["platform"] = platform
                console.print(f"  Redirected to: [cyan]{platform}[/cyan]")
                dismiss_popups(active_page)

            elif mode == "easy_apply":
                return _finish_job(
                    active_page, row, profile, profile_name, pdf_path,
                    indeed_log, "indeed", applied_urls, stats, watchdog,
                    score, fit, keywords, dry_run, review,
                )

            else:  # no_button — tried 15+ selectors, nothing clickable
                print_status("MANUAL_NEEDED", "apply button not found on Indeed after exhaustive search")
                log_result(profile_name, _make_entry(
                    profile_name, row, "button_not_found", pdf_path,
                    score, fit, keywords, notes="Indeed: button_not_found — debug screenshot saved"))
                applied_urls.add(norm_url)
                return "continue"

    # ── 4b. LinkedIn handling ─────────────────────────────────────────────────
    elif platform == "linkedin":
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        watchdog.ping()

        jd_text  = extract_job_description(page, "linkedin")
        pdf_path, score, fit, keywords, fname = pick_resume_with_details(
            title, notes, profile_name, company, jd_text,
        )
        _print_resume_selection(title, company, fname, score, fit, keywords)

        if min_score > 0 and score < min_score and fit == "Low Fit":
            print_status("SKIPPED", f"score {score:.3f} < {min_score} (Low Fit)")
            log_result(profile_name, _make_entry(
                profile_name, row, "skipped_low_fit", pdf_path,
                score, fit, keywords, notes=f"score {score:.3f}"))
            applied_urls.add(norm_url)
            return "continue"

        linkedin_log: list = []
        mode, redirect_page = handle_linkedin_apply(
            page, context, profile, profile_name, pdf_path,
            linkedin_log, company, title,
        )
        watchdog.ping()
        console.print(f"  LinkedIn mode: [cyan]{mode}[/cyan]")

        if mode == "company_site":
            active_page = redirect_page
            platform    = detect_platform(active_page.url)
            row["platform"] = platform
            console.print(f"  Redirected to: [cyan]{platform}[/cyan]")
            dismiss_popups(active_page)

        elif mode == "easy_apply":
            return _finish_job(
                page, row, profile, profile_name, pdf_path,
                linkedin_log, "linkedin", applied_urls, stats, watchdog,
                score, fit, keywords, dry_run, review,
                apply_method="easy_apply",
            )

        else:  # no_button — tried 18+ selectors, nothing clickable
            print_status("MANUAL_NEEDED", "apply button not found on LinkedIn after exhaustive search")
            log_result(profile_name, _make_entry(
                profile_name, row, "button_not_found", pdf_path,
                score, fit, keywords, notes="LinkedIn: button_not_found — debug screenshot saved"))
            applied_urls.add(norm_url)
            return "continue"

    # ── 5. JD + resume selection (non-LinkedIn/Indeed, or redirect fallthrough) ─
    if not pdf_path:
        jd_text = extract_job_description(active_page, platform)
        console.print(f"  JD: {len(jd_text)} chars")
        pdf_path, score, fit, keywords, fname = pick_resume_with_details(
            title, notes, profile_name, company, jd_text,
        )
        _print_resume_selection(title, company, fname, score, fit, keywords)

        # Score gate
        if min_score > 0 and score < min_score and fit == "Low Fit":
            print_status("SKIPPED", f"score {score:.3f} < {min_score} (Low Fit)")
            log_result(profile_name, _make_entry(
                profile_name, row, "skipped_low_fit", pdf_path,
                score, fit, keywords, notes=f"score {score:.3f}"))
            applied_urls.add(norm_url)
            return "continue"
    # (if pdf_path already set by LinkedIn/Indeed block, score/fit/keywords are
    # already correct — no else branch needed)

    watchdog.ping()

    # ── 6. Review mode prompt ─────────────────────────────────────────────────
    if review:
        sal_parsed, sal_label = parse_salary_label(notes, profile_name)
        console.print(Panel(
            f"[bold]Company:[/bold]   {company}\n"
            f"[bold]Title:[/bold]     {title}\n"
            f"[bold]Platform:[/bold]  {platform}\n"
            f"[bold]Salary:[/bold]    {sal_parsed} ({sal_label})\n"
            f"[bold]Resume:[/bold]    {Path(pdf_path).name}\n"
            f"[bold]Score:[/bold]     {score:.2f} — {fit}\n"
            f"[bold]Keywords:[/bold]  {', '.join(keywords[:5])}\n"
            f"[bold]URL:[/bold]       {url[:80]}",
            title="[bold cyan]Review Job[/bold cyan]",
        ))
        while True:
            ans = input("  Apply? (y/n/q): ").strip().lower()
            if ans in ("y", "n", "q"):
                break
        watchdog.ping()
        if ans == "q":
            return "stop"
        if ans == "n":
            print_status("SKIPPED", "manual skip")
            log_result(profile_name, _make_entry(
                profile_name, row, "skipped_manual", pdf_path,
                score, fit, keywords))
            applied_urls.add(norm_url)
            return "continue"

    # ── 7. Dry-run ────────────────────────────────────────────────────────────
    if dry_run:
        print_status("DRY_RUN", f"{Path(pdf_path).name} | {score:.2f} | {fit}")
        log_result(profile_name, _make_entry(
            profile_name, row, "dry_run", pdf_path, score, fit, keywords,
            apply_method="direct_form"))
        stats.record(company, title, score, fit, "dry_run",
                     source_tier=row.get("source_tier", 0))
        applied_urls.add(norm_url)
        return "continue"

    # ── 8. reCAPTCHA check ────────────────────────────────────────────────────
    if detect_recaptcha(active_page):
        print(f"\n  reCAPTCHA detected at {company} - {title}. "
              f"Solve in browser, press Enter to continue.")
        input("  > ")
        watchdog.ping()
        stats.captcha += 1

    if watchdog.timed_out:
        print_status("STUCK", f"watchdog before fill ({watchdog.elapsed():.0f}s)")
        scr = take_screenshot(active_page, company, title, "watchdog")
        log_result(profile_name, _make_entry(
            profile_name, row, "watchdog_timeout", pdf_path, score, fit,
            keywords, screenshot=scr))
        applied_urls.add(norm_url)
        return "continue"

    # ── 9. Fill form ──────────────────────────────────────────────────────────
    console.print("  Filling form...")
    try:
        field_log = fill_form(
            active_page, platform, profile, profile_name,
            pdf_path, company, title,
        )
        watchdog.ping()
    except Exception as e:
        print_status("ERROR", str(e))
        scr = take_screenshot(active_page, company, title, "error")
        log_result(profile_name, _make_entry(
            profile_name, row, "error", pdf_path, score, fit,
            keywords, screenshot=scr, notes=str(e)))
        stats.errors += 1
        applied_urls.add(norm_url)
        return "continue"

    return _finish_job(
        active_page, row, profile, profile_name, pdf_path, field_log,
        platform, applied_urls, stats, watchdog,
        score, fit, keywords, dry_run, review,
    )


def _print_resume_selection(title: str, company: str, fname: str,
                             score: float, fit: str, keywords: list):
    console.print(
        f"\n  [bold][SELECTED_RESUME][/bold]\n"
        f"  Job:      {title} — {company}\n"
        f"  Resume:   [cyan]{fname}[/cyan]\n"
        f"  Score:    {score:.2f}  |  Fit: [{'green' if 'Strong' in fit or 'Good' in fit else 'yellow'}]{fit}[/{'green' if 'Strong' in fit or 'Good' in fit else 'yellow'}]\n"
        f"  Keywords: {', '.join(keywords[:6]) or 'n/a'}"
    )


def _finish_job(active_page, row: dict, profile: dict, profile_name: str,
                pdf_path: str, field_log: list, platform: str,
                applied_urls: set, stats: SessionStats, watchdog: Watchdog,
                score: float, fit: str, keywords: list,
                dry_run: bool, review: bool,
                apply_method: str = "direct_form") -> str:
    """Shared end-of-job: field summary → submit → confirmation → log."""
    url      = str(row.get("url", ""))
    norm_url = normalize_url(url)
    company  = str(row.get("company", ""))
    title    = str(row.get("title", ""))

    print_field_summary(field_log)
    filled_count  = sum(1 for x in field_log if x["status"] == "filled")
    skipped_count = sum(1 for x in field_log if x["status"] == "skipped")

    scr_filled = take_screenshot(active_page, company, title, "filled")

    console.print(
        Panel(
            f"[bold]Company:[/bold]  {company}\n"
            f"[bold]Title:[/bold]    {title}\n"
            f"[bold]Resume:[/bold]   {Path(pdf_path).name}  (score: {score:.2f}, {fit})\n"
            f"[bold]Platform:[/bold] {platform}\n"
            f"[bold]Fields:[/bold]   {filled_count} filled, {skipped_count} skipped\n\n"
            "[yellow]Review the form. Make corrections before answering.[/yellow]",
            title="[bold green]Form Filled — Ready[/bold green]",
        )
    )

    resume_replaced_bool = any(
        e.get("field") == "_meta_resume_replaced" and e.get("status") == "yes"
        for e in field_log
    )
    source_tier = row.get("source_tier", 0)

    if dry_run:
        print_status("DRY_RUN", "would submit here")
        log_result(profile_name, _make_entry(
            profile_name, row, "dry_run", pdf_path, score, fit,
            keywords, screenshot=scr_filled,
            notes=f"{filled_count} filled, {skipped_count} skipped",
            field_log=field_log, apply_method=apply_method))
        stats.record(company, title, score, fit, "dry_run",
                     source_tier=source_tier, apply_method=apply_method,
                     resume_replaced=resume_replaced_bool)
        applied_urls.add(norm_url)
        return "continue"

    # Review mode: ask before submitting. Auto mode: submit immediately.
    if review:
        while True:
            ans = input("  Submit? (y/n/q): ").strip().lower()
            if ans in ("y", "n", "q"):
                break
        watchdog.ping()
        if ans == "q":
            return "stop"
        if ans == "n":
            print_status("SKIPPED", "manual skip")
            log_result(profile_name, _make_entry(
                profile_name, row, "skipped_manual", pdf_path, score, fit, keywords,
                screenshot=scr_filled, field_log=field_log, apply_method=apply_method))
            applied_urls.add(norm_url)
            return "continue"
    # else: auto mode — proceed to submit without prompting

    # ── Submit ────────────────────────────────────────────────────────────────
    if detect_recaptcha(active_page):
        print(f"\n  reCAPTCHA before submit at {company} - {title}. "
              "Solve in browser, press Enter.")
        input("  > ")
        watchdog.ping()
        stats.captcha += 1

    baseline_url = active_page.url
    btn_found    = click_submit(active_page, platform)

    if not btn_found:
        console.print("  [yellow]Submit button not found — submit manually.[/yellow]")
        input("  Press Enter when done...")
        scr = take_screenshot(active_page, company, title, "manual")
        print_status("SUBMITTED", "manual")
        log_result(profile_name, _make_entry(
            profile_name, row, "submitted_manually", pdf_path, score, fit,
            keywords, screenshot=scr, final_url=active_page.url,
            notes=f"{filled_count} filled, {skipped_count} skipped",
            field_log=field_log, apply_method=apply_method))
        stats.record(company, title, score, fit, "submitted_manually",
                     source_tier=source_tier, apply_method=apply_method,
                     resume_replaced=resume_replaced_bool)
        applied_urls.add(norm_url)
        return "continue"

    # ── Confirmation check (max 10s) ──────────────────────────────────────────
    conf_status, conf_detail = wait_for_submission_confirmation(
        active_page, baseline_url, timeout_s=10,
    )

    if conf_status in ("confirmed", "url_changed"):
        scr = take_screenshot(active_page, company, title, "submitted")
        print_status("SUBMITTED", conf_detail)
        log_result(profile_name, _make_entry(
            profile_name, row, "submitted", pdf_path, score, fit,
            keywords, screenshot=scr, final_url=active_page.url,
            notes=f"{filled_count} filled | {conf_detail}",
            field_log=field_log, apply_method=apply_method))
        stats.record(company, title, score, fit, "submitted",
                     source_tier=source_tier, apply_method=apply_method,
                     resume_replaced=resume_replaced_bool)

    else:  # stuck
        scr = take_screenshot(active_page, company, title, "stuck")
        print_status("STUCK", "no confirmation after 10s — marking submit_failed")
        log_result(profile_name, _make_entry(
            profile_name, row, "submit_failed", pdf_path, score, fit,
            keywords, screenshot=scr, final_url=active_page.url,
            notes=conf_detail, field_log=field_log, apply_method=apply_method))
        stats.record(company, title, score, fit, "submit_failed",
                     source_tier=source_tier, apply_method=apply_method,
                     resume_replaced=resume_replaced_bool)

    applied_urls.add(norm_url)
    return "continue"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Job Application Bot")
    parser.add_argument("--profile",   default="muhammad",
                        help="Profile to use: muhammad or razia")
    parser.add_argument("--start-id",  type=int, default=1)
    parser.add_argument("--job-id",    type=int, default=None)
    parser.add_argument("--discover",  action="store_true",
                        help="Auto-discover jobs from resume text after CSV exhausted")
    parser.add_argument("--review",    action="store_true",
                        help="Show each job and ask y/n/q before submitting")
    parser.add_argument("--limit",     type=int, default=50,
                        help="Max jobs per session (default: 50)")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Score + log everything but never submit")
    parser.add_argument("--min-score",      type=float, default=0.0,
                        help="Skip if score < this AND Low Fit (0.0 disables)")
    parser.add_argument("--companies-only", action="store_true",
                        help="Only search Tier 1 company career pages (skip job boards)")
    parser.add_argument("--tier-max",       type=int, default=4,
                        help="Search up to this tier: 1=companies, 2=+Indeed, 3=+LinkedIn, 4=+Google Jobs")
    args = parser.parse_args()

    profile_name = args.profile.lower()
    profile      = load_profile(profile_name)

    jobs_csv = BASE_DIR / "jobs.csv"
    if not jobs_csv.exists():
        console.print("[red]jobs.csv not found.[/red]")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Startup ───────────────────────────────────────────────────────────────
    console.rule("[bold]Job Application Bot[/bold]")
    mode_flags = " ".join(filter(None, [
        "DISCOVER"       if args.discover       else "",
        "COMPANIES-ONLY" if args.companies_only  else "",
        f"TIER-MAX={args.tier_max}" if args.tier_max < 4 else "",
        "REVIEW"         if args.review          else "",
        "DRY-RUN"        if args.dry_run         else "",
        f"LIMIT={args.limit}",
        f"MIN-SCORE={args.min_score}",
    ]))
    console.print(f"  Profile: [cyan]{profile['full_name']}[/cyan]  |  {mode_flags}")
    print_startup_verification(profile_name)

    if args.dry_run:
        console.print("  [cyan][DRY-RUN] Nothing will be submitted.[/cyan]")

    # ── Load jobs ─────────────────────────────────────────────────────────────
    df = pd.read_csv(jobs_csv)
    df = df[df["url"].notna() & (df["url"].str.strip() != "")]
    if args.job_id:
        df = df[df["id"] == args.job_id]
    else:
        df = df[df["id"] >= args.start_id]

    applied_urls = load_applied_urls(profile_name)
    stats        = SessionStats()

    # ── Preview table ─────────────────────────────────────────────────────────
    t = Table(title=f"Jobs — {profile['full_name']}", show_lines=True)
    t.add_column("ID",   style="cyan"); t.add_column("Company"); t.add_column("Title")
    t.add_column("Status", style="yellow"); t.add_column("Notes")
    job_count = 0
    for _, row in df.iterrows():
        if job_count >= args.limit:
            break
        url = normalize_url(str(row.get("url", "")).strip())
        if url in applied_urls:
            row_status = "[dim]done[/dim]"
        else:
            row_status = "[green]queued[/green]"
            job_count += 1
        t.add_row(str(row.get("id","")), str(row.get("company","")),
                  str(row.get("title","")), row_status, str(row.get("notes","")))
    console.print(t)
    console.print(f"  {job_count} jobs queued (limit: {args.limit})\n")

    confirm = input("Start? (y/N): ").strip().lower()
    if confirm != "y":
        console.print("Aborted.")
        return

    console.print(f"\n[bold]Launching browser for {profile['full_name']}...[/bold]")
    browser_dir = BROWSER_PROF / profile_name
    browser_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Remove ALL stale Chrome lock files — singleton locks and every
        # LevelDB LOCK file inside the profile left by unclean shutdowns
        for lf in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            (browser_dir / lf).unlink(missing_ok=True)
        for lock in browser_dir.rglob("LOCK"):
            try:
                lock.unlink()
            except Exception:
                pass

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_dir),
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1440, "height": 900},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()
        user_stopped = False
        jobs_run     = 0

        try:
            # ── Phase 1: CSV jobs ─────────────────────────────────────────────
            for _, row in df.iterrows():
                if jobs_run >= args.limit:
                    console.print(f"\n[yellow]Reached session limit ({args.limit}).[/yellow]")
                    break
                norm = normalize_url(str(row.get("url", "")))
                if norm in applied_urls:
                    stats.duplicates += 1
                    continue
                stats.discovered += 1
                result = process_job(
                    page, context, row.to_dict(), int(row.get("id", 0)),
                    profile, profile_name, applied_urls, stats,
                    dry_run=args.dry_run, review=args.review,
                    min_score=args.min_score,
                )
                jobs_run += 1
                if result == "stop":
                    user_stopped = True
                    console.print("\n[yellow]Stopped by user.[/yellow]")
                    break
                console.print()
                time.sleep(random.uniform(3, 5))

            # ── Phase 2: Discovery ────────────────────────────────────────────
            if not user_stopped and args.discover:
                console.print("\n[bold cyan]Starting autonomous job discovery...[/bold cyan]")
                while jobs_run < args.limit:
                    new_jobs = discover_jobs(
                        page, context, profile_name, applied_urls,
                        max_per_search=20,
                        tier_max=args.tier_max,
                        companies_only=args.companies_only,
                    )
                    if not new_jobs:
                        console.print("  No new jobs found.")
                        break
                    added = append_to_jobs_csv(new_jobs)
                    if not added:
                        break
                    stats.discovered += len(added)
                    for job_row in added:
                        if jobs_run >= args.limit:
                            break
                        result = process_job(
                            page, context, job_row, job_row["id"],
                            profile, profile_name, applied_urls, stats,
                            dry_run=args.dry_run, review=args.review,
                            min_score=args.min_score,
                        )
                        jobs_run += 1
                        if result == "stop":
                            user_stopped = True
                            break
                        console.print()
                        time.sleep(random.uniform(3, 5))
                    if user_stopped:
                        break

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        finally:
            input("\nPress Enter to close browser...")
            try:
                context.close()
            except Exception:
                pass

    stats.print_summary()
    console.print(f"\n[bold green]Done.[/bold green]  "
                  f"Results: {OUTPUT_DIR / f'results_{profile_name}.csv'}")


if __name__ == "__main__":
    main()
