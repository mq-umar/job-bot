#!/usr/bin/env python3
"""
main.py — Job Application Bot

Usage:
  python main.py --profile muhammad
  python main.py --profile razia
  python main.py --profile muhammad --job-id 1
  python main.py --profile muhammad --discover    # auto-finds new jobs after CSV exhausted
"""
import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from form_filler import (
    click_submit, detect_platform, detect_recaptcha,
    extract_job_description, fill_form, fill_indeed_easy_apply,
    find_submit_button, parse_max_salary, wait_for_submission_confirmation,
)
from job_finder import append_to_jobs_csv, discover_jobs
from resume_selector import pick_resume, verify_resumes

console = Console()

BASE_DIR     = Path(__file__).parent
OUTPUT_DIR   = BASE_DIR / "output"
BROWSER_PROF = BASE_DIR / "browser_profile"
MAX_JOB_SECS = 60  # watchdog: seconds before force-skipping a stuck job


# ── Watchdog ──────────────────────────────────────────────────────────────────

class Watchdog:
    """Tracks elapsed time since last ping. Fires after MAX_JOB_SECS of inactivity."""

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
    "SUBMITTED":      "[bold green]",
    "SKIPPED":        "[yellow]",
    "STUCK":          "[bold red]",
    "ERROR":          "[red]",
    "ALREADY_APPLIED":"[dim]",
    "SALARY_GATE":    "[yellow]",
    "SUBMIT_FAILED":  "[bold red]",
}

def print_status(tag: str, detail: str = ""):
    style  = _STATUS_STYLES.get(tag, "[white]")
    close  = style.replace("[", "[/")
    suffix = f"  {detail}" if detail else ""
    console.print(f"  {style}[{tag}]{close}{suffix}")


# ── Profile loading ───────────────────────────────────────────────────────────

def load_profile(name: str) -> dict:
    # Prefer config/ directory, fall back to legacy location
    paths = [
        BASE_DIR / "config" / f"{name}_profile.json",
        BASE_DIR / name / f"{name}_profile.json",
    ]
    for path in paths:
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
    """Return all URLs already submitted/skipped from results CSV."""
    results_csv = OUTPUT_DIR / f"results_{profile_name}.csv"
    applied: set[str] = set()
    if not results_csv.exists():
        return applied
    try:
        with open(results_csv, newline="") as f:
            for row in csv.DictReader(f):
                status = row.get("status", "").lower()
                url    = row.get("url", "").strip()
                if url and status in ("submitted", "submitted_manually",
                                      "skipped", "below salary minimum",
                                      "submit_failed", "watchdog_timeout"):
                    applied.add(url)
    except Exception:
        pass
    return applied


# ── Salary gate ───────────────────────────────────────────────────────────────

def check_salary_gate(profile: dict, notes: str, jd_text: str = "") -> tuple[bool, str]:
    minimum = profile.get("salary_minimum", 0)
    if not minimum:
        return False, ""
    max_found = parse_max_salary(notes) or parse_max_salary(jd_text[:500])
    if max_found and max_found < minimum:
        return True, f"max ${max_found:,} < minimum ${minimum:,}"
    return False, ""


# ── Logging ───────────────────────────────────────────────────────────────────

def log_result(profile_name: str, row: dict, status: str,
               pdf_path: str, notes: str = ""):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_csv = OUTPUT_DIR / f"results_{profile_name}.csv"
    fieldnames  = ["timestamp", "id", "company", "title", "url",
                   "platform", "resume_pdf", "status", "notes"]
    exists = results_csv.exists()
    with open(results_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            "id":         row.get("id", ""),
            "company":    row.get("company", ""),
            "title":      row.get("title", ""),
            "url":        row.get("url", ""),
            "platform":   row.get("platform", ""),
            "resume_pdf": pdf_path,
            "status":     status,
            "notes":      notes,
        })


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
        for x in skipped:
            console.print(f"    • {x['field']} — {x.get('note','')}")
    if errors:
        console.print(f"  Errors ({len(errors)}):", style="red")
        for x in errors:
            console.print(f"    • {x['field']} — {x.get('note','')}")


# ── Screenshot helper ─────────────────────────────────────────────────────────

def take_screenshot(page, path: str):
    try:
        page.screenshot(path=path, timeout=60000, animations="disabled")
        console.print(f"  Screenshot: {path}")
    except Exception as e:
        console.print(f"  [yellow]Screenshot skipped: {e}[/yellow]")


# ── Core job processor ────────────────────────────────────────────────────────

def process_job(page, context, row: dict, row_num: int,
                profile: dict, profile_name: str,
                applied_urls: set) -> str:
    """
    Process one job. Returns "continue" | "stop".
    Handles: deduplication, Indeed modal/new-tab, form fill, watchdog,
    submit confirmation, and clear status reporting.
    """
    url     = str(row.get("url", "")).strip()
    company = str(row.get("company", "Unknown")).strip()
    title   = str(row.get("title",   "Unknown")).strip()
    notes   = str(row.get("notes",   ""))
    pdf_path = ""

    screenshots_dir = OUTPUT_DIR / "screenshots" / profile_name
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold blue]Job {row_num}: {company} — {title}[/bold blue]")
    console.print(f"  URL: {url}")

    watchdog = Watchdog(MAX_JOB_SECS)

    # ── 1. Deduplication ─────────────────────────────────────────────────────
    if url in applied_urls:
        print_status("ALREADY_APPLIED")
        return "continue"

    # ── 2. Navigate ──────────────────────────────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        watchdog.ping()
    except Exception as e:
        print_status("ERROR", f"navigation: {e}")
        log_result(profile_name, {**row, "platform": "unknown"},
                   "error", "", f"nav error: {e}")
        return "continue"

    platform = detect_platform(page.url)
    row["platform"] = platform
    console.print(f"  Platform: [cyan]{platform}[/cyan]")

    # ── 3. Indeed handling ────────────────────────────────────────────────────
    active_page = page
    if platform == "indeed":
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        watchdog.ping()

        if "indeed.com" not in page.url:
            # Redirected before we even clicked — treat as company ATS
            platform = detect_platform(page.url)
            row["platform"] = platform
            console.print(f"  Redirected: [cyan]{platform}[/cyan]  ({page.url[:80]})")
        else:
            jd_early  = extract_job_description(page, "indeed")
            pdf_path  = pick_resume(title, notes, profile_name, company, jd_early)
            console.print(f"  Resume: [cyan]{Path(pdf_path).name}[/cyan]")

            log: list = []
            mode = fill_indeed_easy_apply(
                page, context, profile, profile_name, pdf_path, log, company, title,
            )
            watchdog.ping()
            console.print(f"  Indeed mode: [cyan]{mode}[/cyan]")

            if mode == "company_site":
                active_page = context.pages[-1]
                platform    = detect_platform(active_page.url)
                row["platform"] = platform
                console.print(f"  New tab: [cyan]{platform}[/cyan]  ({active_page.url[:80]})")

            elif mode == "easy_apply":
                return _finish_job(
                    active_page, row, row_num, profile, profile_name,
                    pdf_path, log, "indeed", applied_urls,
                    screenshots_dir, watchdog,
                )
            # mode == "no_button" → fall through to generic fill

    # ── 4. Extract JD (or use early extract from Indeed) ─────────────────────
    if not pdf_path:
        jd_text  = extract_job_description(active_page, platform)
        console.print(f"  JD: {len(jd_text)} chars")
        pdf_path = pick_resume(title, notes, profile_name, company, jd_text)
        console.print(f"  Resume: [cyan]{Path(pdf_path).name}[/cyan]")
    else:
        jd_text = ""

    watchdog.ping()

    # ── 5. Salary gate (Razia) ────────────────────────────────────────────────
    skip, reason = check_salary_gate(profile, notes, jd_text)
    if skip:
        print_status("SALARY_GATE", reason)
        log_result(profile_name, row, "below salary minimum", pdf_path, reason)
        applied_urls.add(url)
        return "continue"

    # ── 6. reCAPTCHA before fill ──────────────────────────────────────────────
    if detect_recaptcha(active_page):
        print("\n  [CAPTCHA] Solve it in the browser, then press Enter...")
        input("  > ")
        watchdog.ping()

    # ── 7. Fill form ──────────────────────────────────────────────────────────
    if watchdog.timed_out:
        print_status("STUCK", f"watchdog fired before fill ({watchdog.elapsed():.0f}s)")
        log_result(profile_name, row, "watchdog_timeout", pdf_path, "timed out before fill")
        applied_urls.add(url)
        return "continue"

    console.print("  Filling form...")
    try:
        field_log = fill_form(
            active_page, platform, profile, profile_name,
            pdf_path, company, title,
        )
        watchdog.ping()
    except Exception as e:
        field_log = [{"field": "fill_form", "status": "error", "note": str(e)}]

    return _finish_job(
        active_page, row, row_num, profile, profile_name,
        pdf_path, field_log, platform, applied_urls,
        screenshots_dir, watchdog,
    )


def _finish_job(active_page, row: dict, row_num: int,
                profile: dict, profile_name: str,
                pdf_path: str, field_log: list, platform: str,
                applied_urls: set, screenshots_dir: Path,
                watchdog: Watchdog) -> str:
    """
    Shared end-of-job path: summary panel → y/n/s → submit with confirmation.
    Returns "continue" | "stop".
    """
    url = str(row.get("url", ""))

    print_field_summary(field_log)
    filled_count  = sum(1 for x in field_log if x["status"] == "filled")
    skipped_count = sum(1 for x in field_log if x["status"] == "skipped")

    take_screenshot(active_page, str(screenshots_dir / f"{row_num:02d}_filled.png"))

    console.print(
        Panel(
            f"[bold]Profile:[/bold]  {profile['full_name']}\n"
            f"[bold]Company:[/bold]  {row.get('company','')}\n"
            f"[bold]Title:[/bold]    {row.get('title','')}\n"
            f"[bold]Resume:[/bold]   {Path(pdf_path).name}\n"
            f"[bold]Platform:[/bold] {platform}\n"
            f"[bold]Fields:[/bold]   {filled_count} filled, {skipped_count} skipped\n\n"
            "[yellow]Review the form. Make manual corrections before answering.[/yellow]",
            title="[bold green]Form Filled — Ready for Review[/bold green]",
        )
    )

    while True:
        answer = input("  Submit? (y / n / s=stop all): ").strip().lower()
        if answer in ("y", "n", "s"):
            break
        console.print("  Enter y, n, or s.")
    watchdog.ping()

    if answer == "s":
        log_result(profile_name, row, "skipped", pdf_path, "user stopped loop")
        return "stop"

    if answer == "n":
        print_status("SKIPPED", "user skipped")
        log_result(profile_name, row, "skipped", pdf_path, "user skipped")
        applied_urls.add(url)
        return "continue"

    # answer == "y" — submit
    if detect_recaptcha(active_page):
        print("\n  [CAPTCHA] Solve before submit, then press Enter...")
        input("  > ")
        watchdog.ping()

    baseline_url = active_page.url
    btn_found    = click_submit(active_page, platform)

    if not btn_found:
        console.print("  [yellow]Submit button not found — submit manually.[/yellow]")
        input("  Press Enter when done...")
        take_screenshot(active_page, str(screenshots_dir / f"{row_num:02d}_manual.png"))
        print_status("SUBMITTED", "manual")
        log_result(profile_name, row, "submitted_manually", pdf_path,
                   f"{filled_count} filled, {skipped_count} skipped")
        applied_urls.add(url)
        return "continue"

    # Wait for confirmation (max 10s)
    conf_status, conf_detail = wait_for_submission_confirmation(
        active_page, baseline_url, timeout_s=10,
    )

    if conf_status in ("confirmed", "url_changed"):
        take_screenshot(active_page, str(screenshots_dir / f"{row_num:02d}_submitted.png"))
        print_status("SUBMITTED", conf_detail)
        log_result(profile_name, row, "submitted", pdf_path,
                   f"{filled_count} filled, {skipped_count} skipped | {conf_detail}")
        applied_urls.add(url)

    elif conf_status == "stuck":
        take_screenshot(active_page, str(screenshots_dir / f"{row_num:02d}_stuck.png"))
        print_status("STUCK", "form unchanged after 10s — marking submit_failed")
        log_result(profile_name, row, "submit_failed", pdf_path,
                   f"stuck on form after click | {conf_detail}")
        applied_urls.add(url)

    return "continue"


# ── Startup verification ──────────────────────────────────────────────────────

def print_startup_verification(profile_name: str):
    found, total, missing = verify_resumes(profile_name)
    if missing:
        console.print(
            f"  Resumes: [yellow]{found}/{total} found[/yellow] "
            f"([red]{len(missing)} missing[/red])"
        )
        for m in missing[:5]:
            console.print(f"    [red]✗[/red] {m}")
        if len(missing) > 5:
            console.print(f"    ... and {len(missing)-5} more")
    else:
        console.print(f"  Resumes: [green]{found}/{total} all found[/green]")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Job Application Bot")
    parser.add_argument("--profile",   default="muhammad")
    parser.add_argument("--start-id",  type=int, default=1)
    parser.add_argument("--job-id",    type=int, default=None)
    parser.add_argument("--discover",  action="store_true",
                        help="Auto-discover new jobs on LinkedIn after CSV is exhausted")
    args = parser.parse_args()

    profile_name = args.profile.lower()
    profile      = load_profile(profile_name)

    jobs_csv = BASE_DIR / "jobs.csv"
    if not jobs_csv.exists():
        console.print("[red]jobs.csv not found.[/red]")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Startup info ─────────────────────────────────────────────────────────
    console.rule("[bold]Job Application Bot[/bold]")
    console.print(f"  Profile: [cyan]{profile['full_name']}[/cyan]")
    print_startup_verification(profile_name)

    # ── Load jobs ─────────────────────────────────────────────────────────────
    df = pd.read_csv(jobs_csv)
    df = df[df["url"].notna() & (df["url"].str.strip() != "")]
    if args.job_id:
        df = df[df["id"] == args.job_id]
    else:
        df = df[df["id"] >= args.start_id]

    if df.empty:
        console.print("[yellow]No jobs to process.[/yellow]")
        return

    applied_urls = load_applied_urls(profile_name)
    if applied_urls:
        console.print(f"  Applied URLs loaded: [dim]{len(applied_urls)}[/dim]")

    # ── Preview table ─────────────────────────────────────────────────────────
    t = Table(title=f"Jobs — {profile['full_name']}", show_lines=True)
    t.add_column("ID",      style="cyan")
    t.add_column("Company")
    t.add_column("Title")
    t.add_column("Resume",  style="green")
    t.add_column("Status",  style="yellow")
    t.add_column("Notes")
    for _, row in df.iterrows():
        url   = str(row.get("url",     "")).strip()
        notes = str(row.get("notes",   ""))
        title = str(row.get("title",   ""))
        comp  = str(row.get("company", ""))
        try:
            pdf = pick_resume(title, notes, profile_name, comp)
            pdf_name = Path(pdf).name
        except Exception:
            pdf_name = "?"
        skip, _ = check_salary_gate(profile, notes)
        if url in applied_urls:
            row_status = "[dim]done[/dim]"
        elif skip:
            row_status = "[yellow]salary gate[/yellow]"
        else:
            row_status = "[green]queued[/green]"
        t.add_row(str(row.get("id","")), comp, title, pdf_name, row_status, notes)
    console.print(t)
    console.print()

    confirm = input("Start? (y/N): ").strip().lower()
    if confirm != "y":
        console.print("Aborted.")
        return

    console.print(f"\n[bold]Launching browser for {profile['full_name']}...[/bold]")

    browser_dir = BROWSER_PROF / profile_name
    browser_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900},
        )
        try:
            Stealth().use_sync(context)
        except Exception:
            pass

        page = context.new_page()
        user_stopped = False

        try:
            # ── Phase 1: Process jobs from CSV ────────────────────────────────
            for _, row in df.iterrows():
                result = process_job(
                    page, context, row.to_dict(), int(row.get("id", 0)),
                    profile, profile_name, applied_urls,
                )
                if result == "stop":
                    user_stopped = True
                    console.print("\n[yellow]Loop stopped by user.[/yellow]")
                    break
                console.print()
                delay = random.uniform(3, 5)
                console.print(f"  Waiting {delay:.1f}s...")
                time.sleep(delay)

            # ── Phase 2: Auto-discover new jobs (if --discover and not stopped) ─
            if not user_stopped and args.discover:
                console.print("\n[bold cyan]Starting autonomous job discovery...[/bold cyan]")
                while True:
                    new_job_dicts = discover_jobs(
                        page, context, profile_name, applied_urls, max_per_search=20,
                    )
                    if not new_job_dicts:
                        console.print("  No new jobs found. Discovery complete.")
                        break

                    added = append_to_jobs_csv(new_job_dicts)
                    if not added:
                        console.print("  All discovered jobs already in jobs.csv.")
                        break

                    for job_row in added:
                        result = process_job(
                            page, context, job_row, job_row["id"],
                            profile, profile_name, applied_urls,
                        )
                        if result == "stop":
                            user_stopped = True
                            break
                        console.print()
                        time.sleep(random.uniform(3, 5))

                    if user_stopped:
                        console.print("\n[yellow]Discovery stopped by user.[/yellow]")
                        break

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        finally:
            input("\nPress Enter to close browser...")
            context.close()

    console.print(
        f"\n[bold green]Done.[/bold green]  "
        f"Results: {OUTPUT_DIR / f'results_{profile_name}.csv'}"
    )


if __name__ == "__main__":
    main()
