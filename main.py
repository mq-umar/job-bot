#!/usr/bin/env python3
"""
main.py - Job Application Bot
Reads jobs.csv, generates a tailored resume per job via Claude API,
renders it as PDF, fills the application form, then pauses for user review.
Run: python main.py [--start-id N]
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from form_filler import detect_platform, extract_job_description, fill_form
from profile import EXPERIENCE_DATA, PROFILE
from resume_generator import generate_resume_pdf, generate_resume_with_claude

load_dotenv()
console = Console()

BASE_DIR     = Path(__file__).parent
OUTPUT_DIR   = BASE_DIR / "output"
RESUMES_DIR  = OUTPUT_DIR / "resumes"
SCREENSHOTS  = OUTPUT_DIR / "screenshots"
RESULTS_CSV  = OUTPUT_DIR / "results.csv"
BROWSER_PROF = BASE_DIR / "browser_profile"

for d in [RESUMES_DIR, SCREENSHOTS, BROWSER_PROF]:
    d.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "_", text)[:40]


def log_result(row: dict, status: str, pdf_path: str, notes: str = ""):
    fieldnames = ["timestamp", "id", "company", "title", "url", "platform",
                  "resume_pdf", "status", "notes"]
    exists = RESULTS_CSV.exists()
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "id":        row.get("id", ""),
            "company":   row.get("company", ""),
            "title":     row.get("title", ""),
            "url":       row.get("url", ""),
            "platform":  row.get("platform", ""),
            "resume_pdf": pdf_path,
            "status":    status,
            "notes":     notes,
        })


def check_api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "your_key_here":
        console.print(
            Panel(
                "[bold red]ANTHROPIC_API_KEY not set.[/bold red]\n"
                "Edit [cyan]job-bot/.env[/cyan] and add your API key:\n"
                "  ANTHROPIC_API_KEY=sk-ant-...",
                title="Missing API Key",
            )
        )
        sys.exit(1)


# ── Core job processor ────────────────────────────────────────────────────────

def process_job(page, row: dict, row_num: int):
    url     = row["url"]
    company = row.get("company", "Unknown")
    title   = row.get("title", "Unknown")

    console.rule(f"[bold blue]Job {row_num}: {company} - {title}[/bold blue]")
    console.print(f"  URL: {url}")

    # 1. Navigate to job page
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
    except Exception as e:
        console.print(f"  [red]Navigation failed: {e}[/red]")
        log_result({**row, "platform": "unknown"}, "navigation_error", "", str(e))
        return

    platform = detect_platform(page.url)
    row["platform"] = platform
    console.print(f"  Platform detected: [cyan]{platform}[/cyan]")

    # If Indeed, wait for redirect to real ATS and re-detect
    if platform == "indeed":
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1.5)
            platform = detect_platform(page.url)
            row["platform"] = platform
            console.print(f"  Redirected to: [cyan]{platform}[/cyan]  ({page.url[:80]})")
        except Exception:
            pass

    # 2. Extract job description
    console.print("  Extracting job description...")
    jd_text = extract_job_description(page, platform)
    if len(jd_text) < 100:
        console.print(f"  [yellow]Short JD ({len(jd_text)} chars) — may be incomplete[/yellow]")
    else:
        console.print(f"  JD extracted: {len(jd_text)} chars")

    # 3. Generate tailored resume via Claude API
    console.print("  [yellow]Generating tailored resume via Claude...[/yellow]")
    try:
        resume_data = generate_resume_with_claude(jd_text, EXPERIENCE_DATA)
        console.print(f"  [green]Resume JSON generated[/green] — summary: {resume_data['summary'][:80]}...")
    except Exception as e:
        console.print(f"  [red]Claude API error: {e}[/red]")
        log_result(row, "api_error", "", str(e))
        return

    # 4. Render PDF
    safe_company = slugify(company) or "company"
    safe_title   = slugify(title)   or "role"
    pdf_filename = f"{row_num:02d}_{safe_company}_{safe_title}.pdf"
    pdf_path     = str(RESUMES_DIR / pdf_filename)

    try:
        generate_resume_pdf(resume_data, pdf_path)
        console.print(f"  [green]PDF saved:[/green] {pdf_path}")
    except Exception as e:
        console.print(f"  [red]PDF generation error: {e}[/red]")
        log_result(row, "pdf_error", "", str(e))
        return

    # 5. Fill application form
    interest_blurb = resume_data.get("interest_blurb", "")
    console.print("  Filling application form...")
    try:
        fill_form(page, platform, PROFILE, pdf_path, interest_blurb)
        console.print("  [green]Form filled[/green]")
    except Exception as e:
        console.print(f"  [yellow]Form fill partial/error: {e}[/yellow]")

    # 6. Screenshot
    try:
        screenshot_path = str(SCREENSHOTS / f"{row_num:02d}_filled.png")
        page.screenshot(path=screenshot_path, timeout=60000, animations="disabled")
        console.print(f"  Screenshot: {screenshot_path}")
    except Exception as e:
        console.print(f"  [yellow]Screenshot skipped: {e}[/yellow]")

    # 7. Pause for user review — DO NOT auto-submit
    console.print(
        Panel(
            f"[bold green]Form filled and ready for review.[/bold green]\n\n"
            f"Resume PDF: [cyan]{pdf_path}[/cyan]\n\n"
            "[yellow]Review the form in the browser window.\n"
            "Make any corrections, then manually click Submit.\n\n"
            "Press Enter here when done (or to skip this job).[/yellow]",
            title=f"[bold]Review: {company} - {title}[/bold]",
        )
    )
    user_input = input("  > Press Enter to continue to next job (Ctrl+C to quit)... ")

    status = "submitted_by_user" if not user_input.strip() else user_input.strip()
    log_result(row, status, pdf_path)
    console.print(f"  Logged as: [cyan]{status}[/cyan]")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Job Application Bot")
    parser.add_argument("--start-id", type=int, default=1,
                        help="Start from this job ID (skip earlier rows)")
    parser.add_argument("--job-id", type=int, default=None,
                        help="Run only this specific job ID")
    args = parser.parse_args()

    check_api_key()

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

    # Show job list
    t = Table(title="Jobs to Process", show_lines=True)
    t.add_column("ID", style="cyan")
    t.add_column("Company")
    t.add_column("Title")
    t.add_column("Priority", style="yellow")
    t.add_column("Notes")
    for _, row in df.iterrows():
        t.add_row(
            str(row.get("id", "")),
            str(row.get("company", "")),
            str(row.get("title", "")),
            str(row.get("priority", "")),
            str(row.get("notes", "")),
        )
    console.print(t)
    console.print()

    confirm = input("Start processing? (y/N): ").strip().lower()
    if confirm != "y":
        console.print("Aborted.")
        return

    console.print("\n[bold]Launching browser...[/bold]")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROF),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            viewport={"width": 1440, "height": 900},
        )

        # Apply stealth to context (adds init scripts to every new page)
        try:
            Stealth().use_sync(context)
        except Exception:
            pass

        page = context.new_page()

        try:
            for _, row in df.iterrows():
                process_job(page, row.to_dict(), int(row.get("id", 0)))
                console.print()
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/yellow]")
        finally:
            input("\nPress Enter to close browser...")
            context.close()

    console.print(f"\n[bold green]Done! Results logged to:[/bold green] {RESULTS_CSV}")


if __name__ == "__main__":
    main()
