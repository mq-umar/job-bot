#!/usr/bin/env python3
"""
main.py - Job Application Bot
Full end-to-end: open job URL → fill form → upload resume → review → submit.

Usage:
  python main.py --profile muhammad
  python main.py --profile razia
  python main.py --profile muhammad --job-id 1
  python main.py --profile razia   --start-id 3
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

import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from form_filler import (
    click_submit, detect_platform, detect_recaptcha,
    extract_job_description, fill_form, find_submit_button, parse_max_salary,
)
from resume_selector import pick_resume

console = Console()

BASE_DIR     = Path(__file__).parent
OUTPUT_DIR   = BASE_DIR / "output"
BROWSER_PROF = BASE_DIR / "browser_profile"


# ── Profile loading ───────────────────────────────────────────────────────────

def load_profile(name: str) -> dict:
    path = BASE_DIR / name / f"{name}_profile.json"
    if not path.exists():
        console.print(f"[red]Profile not found: {path}[/red]")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    # Derive phone_formatted
    if "phone_formatted" not in data and "phone" in data:
        p = data["phone"]
        data["phone_formatted"] = (
            f"({p[:3]}) {p[3:6]}-{p[6:]}" if len(p) == 10 and p.isdigit() else p
        )
    return data


# ── Salary gate (Razia only) ──────────────────────────────────────────────────

def check_salary_gate(profile: dict, notes: str, jd_text: str = "") -> tuple[bool, str]:
    """
    If the profile has a salary_minimum > 0, check whether the job's max
    salary (parsed from notes or JD) is below that threshold.
    Returns (should_skip, reason_string).
    """
    minimum = profile.get("salary_minimum", 0)
    if not minimum:
        return False, ""
    max_found = parse_max_salary(notes) or parse_max_salary(jd_text[:500])
    if max_found and max_found < minimum:
        return True, f"below salary minimum (max found: ${max_found:,}, minimum: ${minimum:,})"
    return False, ""


# ── Logging ───────────────────────────────────────────────────────────────────

def log_result(profile_name: str, row: dict, status: str,
               pdf_path: str, notes: str = ""):
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

    console.print(f"\n  Fields filled  ({len(filled)}):", style="green")
    for x in filled:
        val = x.get("value", "")
        console.print(f"    • {x['field']}: {val}")

    if skipped:
        console.print(f"\n  Fields skipped ({len(skipped)}):", style="yellow")
        for x in skipped:
            console.print(f"    • {x['field']} — {x.get('note','')}")

    if errors:
        console.print(f"\n  Errors ({len(errors)}):", style="red")
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

def process_job(page, row: dict, row_num: int,
                profile: dict, profile_name: str) -> str:
    """
    Returns "continue", "stop", or "skip".
    """
    url     = row["url"]
    company = str(row.get("company", "Unknown")).strip()
    title   = str(row.get("title",   "Unknown")).strip()
    notes   = str(row.get("notes",   ""))

    screenshots_dir = OUTPUT_DIR / "screenshots" / profile_name
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold blue]Job {row_num}: {company} — {title}[/bold blue]")
    console.print(f"  URL: {url}")

    # 1. Pick resume
    pdf_path = pick_resume(title, notes, profile_name)
    console.print(f"  Resume: [cyan]{Path(pdf_path).name}[/cyan]")

    # 2. Navigate
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
    except Exception as e:
        console.print(f"  [red]Page error: {e}[/red]")
        log_result(profile_name, {**row, "platform": "unknown"},
                   "error", pdf_path, f"page error: {e}")
        return "continue"

    platform = detect_platform(page.url)
    row["platform"] = platform
    console.print(f"  Platform: [cyan]{platform}[/cyan]")

    # 3. Re-detect after Indeed redirect
    if platform == "indeed":
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1.5)
            new_platform = detect_platform(page.url)
            if new_platform != "indeed":
                platform = new_platform
                row["platform"] = platform
                console.print(f"  Redirected to: [cyan]{platform}[/cyan]  ({page.url[:80]})")
        except Exception:
            pass

    # 4. Extract JD text
    jd_text = extract_job_description(page, platform)
    console.print(f"  JD: {len(jd_text)} chars")

    # 5. Salary gate (Razia)
    skip, reason = check_salary_gate(profile, notes, jd_text)
    if skip:
        console.print(f"  [yellow]Skipping: {reason}[/yellow]")
        log_result(profile_name, row, "below salary minimum", pdf_path, reason)
        return "continue"

    # 6. reCAPTCHA check before filling
    if detect_recaptcha(page):
        print("\n  [CAPTCHA] reCAPTCHA detected — solve it in the browser, then press Enter...")
        input("  > ")

    # 7. Fill form
    console.print("  Filling form...")
    try:
        field_log = fill_form(
            page, platform, profile, profile_name,
            pdf_path, company, title,
        )
    except Exception as e:
        console.print(f"  [red]Fill error: {e}[/red]")
        field_log = [{"field": "fill_form", "status": "error", "note": str(e)}]

    # 8. Print field summary
    print_field_summary(field_log)
    filled_count  = sum(1 for x in field_log if x["status"] == "filled")
    skipped_count = sum(1 for x in field_log if x["status"] == "skipped")

    # 9. Screenshot of completed form
    take_screenshot(page, str(screenshots_dir / f"{row_num:02d}_filled.png"))

    # 10. Summary panel + ask user
    console.print(
        Panel(
            f"[bold]Profile:[/bold]  {profile['full_name']}\n"
            f"[bold]Company:[/bold]  {company}\n"
            f"[bold]Title:[/bold]    {title}\n"
            f"[bold]Resume:[/bold]   {Path(pdf_path).name}\n"
            f"[bold]Platform:[/bold] {platform}\n"
            f"[bold]Fields:[/bold]   {filled_count} filled, {skipped_count} skipped\n\n"
            "[yellow]Review the form in the browser window.\n"
            "Make any manual corrections before answering.[/yellow]",
            title="[bold green]Form Filled — Ready for Review[/bold green]",
        )
    )

    # 11. Prompt
    while True:
        answer = input("  Submit this application? (y / n / s=stop all): ").strip().lower()
        if answer in ("y", "n", "s"):
            break
        console.print("  Please enter y, n, or s.")

    if answer == "s":
        log_result(profile_name, row, "skipped", pdf_path, "user stopped loop")
        return "stop"

    if answer == "n":
        console.print("  Skipped.")
        log_result(profile_name, row, "skipped", pdf_path, "user skipped")
        return "continue"

    # answer == "y" — submit
    console.print("  Submitting...")

    # reCAPTCHA one more time before submit click
    if detect_recaptcha(page):
        print("\n  [CAPTCHA] reCAPTCHA before submit — solve it, then press Enter...")
        input("  > ")

    submitted = click_submit(page, platform)

    if submitted:
        console.print("  [bold green]Submitted![/bold green]")
        take_screenshot(page, str(screenshots_dir / f"{row_num:02d}_submitted.png"))
        log_result(profile_name, row, "submitted", pdf_path,
                   f"{filled_count} fields filled, {skipped_count} skipped")
    else:
        console.print("  [yellow]Submit button not found — submit manually in the browser.[/yellow]")
        input("  Press Enter when done...")
        take_screenshot(page, str(screenshots_dir / f"{row_num:02d}_manual.png"))
        log_result(profile_name, row, "submitted_manually", pdf_path,
                   f"{filled_count} fields filled, {skipped_count} skipped")

    return "continue"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Job Application Bot")
    parser.add_argument("--profile", default="muhammad",
                        help="Profile folder name (e.g. muhammad, razia)")
    parser.add_argument("--start-id", type=int, default=1,
                        help="Start from this job ID")
    parser.add_argument("--job-id", type=int, default=None,
                        help="Run only this specific job ID")
    args = parser.parse_args()

    profile_name = args.profile.lower()
    profile      = load_profile(profile_name)

    jobs_csv = BASE_DIR / "jobs.csv"
    if not jobs_csv.exists():
        console.print("[red]jobs.csv not found.[/red]")
        sys.exit(1)

    df = pd.read_csv(jobs_csv)
    df = df[df["url"].notna() & (df["url"].str.strip() != "")]

    if args.job_id:
        df = df[df["id"] == args.job_id]
    else:
        df = df[df["id"] >= args.start_id]

    if df.empty:
        console.print("[yellow]No jobs to process.[/yellow]")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Preview table
    t = Table(title=f"Jobs — {profile['full_name']}", show_lines=True)
    t.add_column("ID",      style="cyan")
    t.add_column("Company")
    t.add_column("Title")
    t.add_column("Resume",  style="green")
    t.add_column("Notes")
    for _, row in df.iterrows():
        pdf   = pick_resume(str(row.get("title", "")), str(row.get("notes", "")), profile_name)
        notes = str(row.get("notes", ""))
        # Flag salary-gated jobs in the preview
        skip, reason = check_salary_gate(profile, notes)
        gate_flag = " [yellow](salary gate)[/yellow]" if skip else ""
        t.add_row(
            str(row.get("id", "")),
            str(row.get("company", "")),
            str(row.get("title", "")) + gate_flag,
            Path(pdf).name,
            notes,
        )
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

        try:
            for _, row in df.iterrows():
                result = process_job(
                    page, row.to_dict(), int(row.get("id", 0)),
                    profile, profile_name,
                )
                if result == "stop":
                    console.print("\n[yellow]Loop stopped by user.[/yellow]")
                    break
                console.print()

                # 3–5 second random delay between jobs
                delay = random.uniform(3, 5)
                console.print(f"  Waiting {delay:.1f}s before next job...")
                time.sleep(delay)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        finally:
            input("\nPress Enter to close browser...")
            context.close()

    results_csv = OUTPUT_DIR / f"results_{profile_name}.csv"
    console.print(f"\n[bold green]Done. Results:[/bold green] {results_csv}")


if __name__ == "__main__":
    main()
