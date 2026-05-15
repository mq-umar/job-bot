#!/usr/bin/env python3
"""
test_instride.py
Full integration test against InStride Health Greenhouse form.
Uses a hardcoded mock resume (no Claude API call needed) so you can verify
browser filling works before adding your ANTHROPIC_API_KEY to .env

Run: python test_instride.py
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from rich.console import Console

from form_filler import detect_platform, extract_job_description, fill_greenhouse
from profile import PROFILE
from resume_generator import generate_resume_pdf

console = Console()

URL = "https://job-boards.greenhouse.io/instridehealth/jobs/4687890005"
PDF_PATH = str(Path(__file__).parent / "output" / "resumes" / "test_instride_live.pdf")

MOCK_RESUME = {
    "summary": (
        "IT support professional with hands-on experience administering Microsoft 365, Entra ID, "
        "and Intune across distributed environments. Managed end-to-end device lifecycle, identity "
        "governance, and Tier 2 escalations at a financial institution and a multi-location business. "
        "Built automation workflows in Python and PowerShell to reduce manual IT processes. "
        "Ready to bring the same rigor to InStride Health's distributed clinical team."
    ),
    "skills": [
        {"label": "Identity & IAM",  "items": "Entra ID, Azure AD, SSO, MFA, Conditional Access, SCIM Provisioning, RBAC"},
        {"label": "MDM & Endpoints", "items": "Microsoft Intune, MDM/UEM, Device Enrollment, Compliance Policies, macOS & Windows"},
        {"label": "M365 & Cloud",    "items": "Microsoft 365, Exchange Online, Teams, SharePoint, OneDrive, Azure, AWS"},
        {"label": "Support & ITSM",  "items": "Tier 1/Tier 2 Escalation, Help Desk, Root Cause Analysis, Asset Management"},
        {"label": "Automation",      "items": "Python, PowerShell, REST API Integration, Workflow Automation"},
        {"label": "Languages",       "items": "Python, PowerShell, JavaScript, SQL, Java, C++, PHP, HTML/CSS"},
    ],
    "tony_bullets": [
        "Implemented <b>Entra ID</b> with SSO, MFA, and Conditional Access policies, establishing enterprise-grade identity governance across all company systems.",
        "Deployed <b>Microsoft Intune</b> for MDM device enrollment, compliance policy enforcement, and remote endpoint management across all company devices.",
        "Owned end-to-end <b>onboarding and offboarding workflows</b> including account provisioning, device imaging, and secure access removal.",
        "Served as final escalation tier for hardware, software, networking, and access issues, maintaining high system availability with minimal downtime.",
        "Built Python and PowerShell automation to integrate POS systems and third-party platforms, eliminating manual data processes.",
    ],
    "jovia_bullets": [
        "Served as primary incident responder during the 2024 global <b>CrowdStrike</b> outage, diagnosing root cause and restoring executive systems under time pressure.",
        "Administered <b>Microsoft 365, Azure AD</b>, and Azure Virtual Desktop environments — managing user accounts, permissions, and licensing.",
        "Developed PowerShell and Python scripts to automate asset tracking and reporting, reducing manual effort significantly.",
    ],
    "tony_title": "IT Supervisor - Identity, Endpoint & Systems Administration",
    "interest_blurb": (
        "InStride Health's focus on delivering specialty anxiety and OCD care to underserved populations "
        "resonates with me because I've seen firsthand how operational and technical gaps create barriers "
        "to care access. I want to bring my background in endpoint management, identity governance, and "
        "IT automation to a team where reliable systems directly support clinicians serving kids and families."
    ),
}


def main():
    console.rule("[bold blue]InStride Health - Full Integration Test[/bold blue]")

    # Step 1: Generate PDF from mock resume
    console.print("  Generating test PDF resume...")
    generate_resume_pdf(MOCK_RESUME, PDF_PATH)
    console.print(f"  [green]PDF saved:[/green] {PDF_PATH}")

    # Step 2: Launch browser, fill form, pause for review
    console.print("\n  Launching browser (headless=False so you can see it)...")
    console.print("  [yellow]The browser will open. Check the filled form, then press Enter here.[/yellow]\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(Path(__file__).parent / "browser_profile"),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport={"width": 1440, "height": 900},
        )

        try:
            Stealth().use_sync(context)
        except Exception as e:
            console.print(f"  [yellow]Stealth warning: {e}[/yellow]")

        page = context.new_page()

        # Navigate
        console.print(f"  Opening: {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        platform = detect_platform(page.url)
        console.print(f"  Platform: [cyan]{platform}[/cyan]")

        # Extract JD
        jd = extract_job_description(page, platform)
        console.print(f"  JD extracted: {len(jd)} chars")

        # Fill form
        console.print("  Filling form fields...")
        fill_greenhouse(
            page,
            PROFILE,
            PDF_PATH,
            interest_blurb=MOCK_RESUME["interest_blurb"],
        )
        console.print("  [green]Form filled[/green]")

        # Screenshot
        screenshot_path = str(Path(__file__).parent / "output" / "screenshots" / "test_instride_filled.png")
        page.screenshot(path=screenshot_path, timeout=60000, animations="disabled")
        console.print(f"  Screenshot: {screenshot_path}")

        input("\n  Review the form in the browser. Press Enter to close... ")
        context.close()

    console.print("\n[bold green]Test complete.[/bold green]")
    console.print("If the form looked correct, add your ANTHROPIC_API_KEY to .env and run:")
    console.print("  [cyan]python main.py --job-id 1[/cyan]")


if __name__ == "__main__":
    main()
