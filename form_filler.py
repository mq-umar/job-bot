"""
form_filler.py
Comprehensive ATS form filling: fuzzy label matching, cover letter generation,
salary detection, reCAPTCHA pause, file upload, and submit handling.
"""
import random
import re
import time
from pathlib import Path
from typing import Optional

# ── Skills lookup (resume filename → 2-3 relevant skills phrase) ──────────────

SKILLS_BY_RESUME = {
    # Cluster resumes
    "C1_M365_Azure_Intune_Admin.pdf":      "Microsoft 365, Entra ID SSO/MFA, and Intune MDM administration",
    "C2_Systems_Administrator.pdf":         "systems administration, Microsoft 365, and PowerShell automation",
    "C3_MSP_Managed_Services.pdf":          "managed IT services, help desk escalation, and endpoint deployment",
    "C4_Cloud_Infrastructure_Engineer.pdf": "Azure cloud infrastructure, serverless deployment, and REST API integration",
    "C5_Cybersecurity_Security_Analyst.pdf":"identity security controls, MFA/Conditional Access, and incident response",
    "C6_Network_Engineer_Admin.pdf":        "network administration, TCP/IP troubleshooting, and cloud-connected infrastructure",
    "C7_IT_Support_Specialist.pdf":         "Tier 2 IT support, Microsoft 365 administration, and endpoint lifecycle management",
    "C8_IAM_Identity_Engineer.pdf":         "Entra ID identity governance, SSO/MFA, and SCIM automated provisioning",
    "C9_IT_Manager_Director.pdf":           "IT strategy, full-stack infrastructure ownership, and executive partnership",
    "C10_DevOps_Cloud_Automation.pdf":      "serverless infrastructure, Python/PowerShell automation, and API pipeline design",
    # JD-specific numbered resumes
    "01_IBM_AI_First_Strategy_Consultant.pdf":          "AI strategy consulting, digital transformation, and enterprise innovation",
    "02_IBM_Associate_Data_Scientist_2026.pdf":         "machine learning, Python data science, and predictive analytics",
    "03_IBM_Application_Developer_Azure_Cloud.pdf":     "Azure cloud migration, application development, and cloud-native architecture",
    "04_IBM_Software_Engineer_Apprentice_A.pdf":        "software engineering, Python development, and cloud API integration",
    "05_IBM_Software_Engineer_Apprentice_B.pdf":        "software engineering, backend development, and IBM platform integration",
    "06_IBM_AI_Software_Developer.pdf":                 "AI software development, Watsonx LLM integration, and intelligent automation",
    "07_IBM_System_Support_Tech_Apprentice.pdf":        "IT systems support, hardware troubleshooting, and technical operations",
    "08_IBM_Backend_Developer_Intern_2026.pdf":         "backend API development, REST services, and cloud platform integration",
    "09_Dev10_Entry_Level_Data_Engineer.pdf":           "data engineering, ETL pipeline design, and Snowflake/Airflow workflows",
    "10_StepStone_Junior_Analyst_RFP_AI.pdf":           "AI-assisted content analysis, RFP management, and Power Automate workflows",
    "11_Imprint_Software_Engineer.pdf":                 "Go/Python microservices, fintech API integration, and DynamoDB data modeling",
    "12_IT_Project_Manager.pdf":                        "IT project delivery, Agile/Scrum facilitation, and JIRA sprint management",
    "13_Tinder_Product_Analyst.pdf":                    "product analytics, A/B experimentation, and funnel optimization with SQL/Tableau",
    "14_FlexTrade_Software_Developer_Cpp.pdf":          "C++ trading system development, EMS/OEMS integration, and Qt UI",
    "15_HomeServe_DevOps_Engineer.pdf":                 "AWS DevOps, GitHub Actions CI/CD, and CloudFormation infrastructure-as-code",
    "16_Intuit_Software_Engineer_1.pdf":                "full-stack development, React/Spring Boot, and scalable web application design",
    "17_FullStack_Backend_Engineer.pdf":                "Python/FastAPI backend engineering, REST API design, and cloud-native deployment",
    "18_Deloitte_Forward_Deployed_Engineer.pdf":        "GenAI consulting, Azure AI Foundry RAG pipelines, and LLMOps at scale",
    "19_Honeywell_Software_Engineer_Recent_Grad.pdf":   "software engineering fundamentals, Python scripting, and system integration",
    "20_BrandRankAI_Frontend_Software_Engineer.pdf":    "Deno/Fresh frontend engineering, data-rich dashboard development, and Core Web Vitals",
    # IT-specific job resumes
    "Resume_InStride_Updated.pdf":                      "IT support, Microsoft 365 administration, and endpoint lifecycle management",
    "Job_PASONA_IT_Infrastructure_Engineer.pdf":        "IT infrastructure engineering, Microsoft 365, and cloud platform administration",
    "Job_IT_Service_Engineer.pdf":                      "IT service management, systems administration, and infrastructure support",
    "Job_Skopein_IT_Support_Engineer_L2.pdf":           "Level II IT support, network troubleshooting, and endpoint deployment",
    "Job_Google_CES_AI_Integration.pdf":                "GCP AI integration, Contact Center AI, and Node.js API development",
    "Job_AI_Product_Engineer.pdf":                      "AI product engineering, Claude/LLM integration, and rapid prototyping",
    "Resume_BackEnd_Developer.pdf":                     "Java/Spring Boot backend development, AWS Lambda, and REST API design",
    "Resume_Data_Analyst.pdf":                          "Power BI reporting, SQL analytics, and healthcare KPI dashboards",
    "Resume_Process_Automation_Engineer_FINAL.pdf":     "process automation, Power BI, and continuous improvement engineering",
    # Razia resumes
    "RC1_Vulnerability_Management.pdf":     "vulnerability assessment, patch lifecycle management, and compliance reporting",
    "RC2_Endpoint_Security_Intune.pdf":     "Intune MDM, endpoint security policy enforcement, and compliance management",
    "RC3_macOS_Apple_MDM.pdf":              "macOS fleet management, Apple MDM, and endpoint security configuration",
    "RC4_Patch_Management_Compliance.pdf":  "patch management, compliance tracking, and endpoint remediation",
    "RC5_SOC_Security_Analyst.pdf":         "SOC operations, threat detection and analysis, and incident response",
    "RC6_IT_Security_Engineer.pdf":         "IT security engineering, identity governance, and endpoint protection",
    "RC7_Cloud_Azure_Security.pdf":         "Azure security architecture, cloud identity protection, and compliance frameworks",
    "RC8_Government_Defense.pdf":           "government IT security, compliance frameworks, and secure system administration",
}

_MUHAMMAD_COVER = (
    "I am excited to apply for the {title} role at {company}. "
    "My hands-on experience with {skills} makes me a strong match. "
    "I am completing my B.S. in Computer Programming at Farmingdale State College "
    "(May 2026, GPA 3.66) while working full-time as IT Supervisor at Tony's Tacos "
    "where I built the company's full Microsoft 365 environment from scratch. "
    "I would love to bring that same ownership mindset to your team."
)

_RAZIA_COVER = (
    "I am excited to apply for the {title} role at {company}. "
    "My background in {skills} positions me well for this opportunity. "
    "I am a detail-oriented IT security professional with hands-on experience "
    "implementing security controls, managing endpoints, and working in "
    "compliance-driven environments. I would welcome the opportunity to "
    "contribute to your team."
)


def get_cover_letter(title: str, company: str, resume_name: str, profile_name: str,
                     matched_keywords=None) -> str:
    if matched_keywords:
        # Use actual JD-matched terms for a more targeted cover letter
        kw_str = ", ".join(matched_keywords[:3]) or "technology and problem-solving"
        return (
            f"I am applying for the {title or 'this'} role at {company or 'your organization'}. "
            f"My background in {kw_str} aligns with your requirements. "
            f"I would welcome the opportunity to discuss how I can contribute to your team."
        )
    skills   = SKILLS_BY_RESUME.get(resume_name, "IT support, systems administration, and security")
    template = _RAZIA_COVER if profile_name == "razia" else _MUHAMMAD_COVER
    return template.format(
        title=title or "this position",
        company=company or "your organization",
        skills=skills,
    )


# ── Salary helpers ────────────────────────────────────────────────────────────

def parse_max_salary(text: str) -> Optional[int]:
    """Return the maximum annual salary integer from text like '$64-72K' or '$70-100K'."""
    text = text.replace(",", "")
    m = re.search(r'\$?(\d+)\s*[kK]?\s*[-–]\s*\$?(\d+)\s*[kK]', text, re.I)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi < 2000:
            hi *= 1000
        if lo < 2000:
            lo *= 1000
        return hi
    m = re.search(r'\$(\d+)\s*[kK]', text, re.I)
    if m:
        v = int(m.group(1))
        return v * 1000 if v < 2000 else v
    return None


def _salary_value(el, profile: dict, label_lower: str) -> str:
    """Pick the right salary value based on field type and whether it's min/max."""
    if "min" in label_lower:
        return str(profile.get("salary_min", profile.get("salary_number", 70000)))
    if "max" in label_lower:
        return str(profile.get("salary_max", profile.get("salary_number", 90000)))
    input_type = (el.get_attribute("type") or "text").lower()
    if input_type == "number":
        return str(profile.get("salary_number", 75000))
    # Check for numeric-only placeholder
    placeholder = (el.get_attribute("placeholder") or "").strip()
    if placeholder.isdigit() or re.match(r'^\d[\d,]+$', placeholder):
        return str(profile.get("salary_number", 75000))
    return profile.get("salary_text", "Negotiable")


# ── Human simulation ──────────────────────────────────────────────────────────

def human_delay(min_s: float = 0.4, max_s: float = 1.0):
    time.sleep(random.uniform(min_s, max_s))


# ── Platform detection ────────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    url = url.lower()
    if "greenhouse.io"    in url: return "greenhouse"
    if "lever.co"         in url: return "lever"
    if "workday"          in url: return "workday"
    if "ashbyhq.com"      in url: return "ashby"
    if "icims.com"        in url: return "icims"
    if "taleo"            in url: return "taleo"
    if "smartrecruiters"  in url: return "smartrecruiters"
    if "linkedin.com"     in url: return "linkedin"
    if "indeed.com"       in url: return "indeed"
    return "generic"


# ── Job description extraction ────────────────────────────────────────────────

def extract_job_description(page, platform: str) -> str:
    selectors = {
        "greenhouse":      ["#content", ".job-post__description",
                            "[data-qa='job-description']", "section.content",
                            ".job__description"],
        "lever":           [".posting-requirements", ".section-wrapper",
                            "[class*='description']", ".posting-content"],
        "workday":         ["[data-automation-id='job-description']",
                            "[class*='rich-text-container']", "[class*='wd-text']",
                            "section[class*='description']", "div[class*='jobPosting']"],
        "ashby":           ["[class*='job-description']", "[class*='JobDescription']",
                            "div[data-testid*='description']", "main"],
        "icims":           [".iCIMS_JobContent", "[id*='description']",
                            "[class*='job-description']"],
        "taleo":           ["[id*='description']", "[class*='requisition']",
                            "div.jobDescription"],
        "smartrecruiters": [".job-description", "[data-ui='job-description']",
                            "[class*='jobad-details']"],
        "indeed":          ["#jobDescriptionText", ".jobsearch-jobDescriptionText",
                            "[data-testid='jobsearch-JobComponent-description']"],
        "linkedin":        [".jobs-description__content", ".jobs-box__html-content",
                            ".job-view-layout .description__text",
                            "[class*='jobs-description']", "article"],
        "generic":         ["[class*='job-description']", "[class*='jobDescription']",
                            "[class*='job-details']", "[class*='description']",
                            "main", "article", "#content", "#main"],
    }
    for sel in selectors.get(platform, selectors["generic"]):
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                if len(text) > 300:
                    return text.strip()[:20000]
        except Exception:
            pass
    # Generic fallback — try all generic selectors too
    if platform != "generic":
        for sel in selectors["generic"]:
            try:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text()
                    if len(text) > 300:
                        return text.strip()[:20000]
            except Exception:
                pass
    try:
        return page.inner_text("body")[:20000]
    except Exception:
        return ""


# ── reCAPTCHA detection ───────────────────────────────────────────────────────

def detect_recaptcha(page) -> bool:
    """
    Returns True only for VISIBLE reCAPTCHA challenges that require user action.
    Invisible reCAPTCHA (size=invisible) runs silently — we ignore those.
    """
    try:
        # Visible checkbox widget
        visible_widget = page.query_selector(".g-recaptcha:visible, [data-sitekey]:visible")
        if visible_widget:
            return True
        # iFrames that are NOT invisible mode
        for iframe in page.query_selector_all("iframe[src*='recaptcha'], iframe[title*='reCAPTCHA']"):
            src = iframe.get_attribute("src") or ""
            if "size=invisible" not in src:
                return True
        return False
    except Exception:
        return False


# ── Popup / cookie banner dismissal ──────────────────────────────────────────

def dismiss_popups(page) -> None:
    """Auto-dismiss cookie banners and modal popups before interacting with a page."""
    selectors = [
        "button:has-text('Accept All')", "button:has-text('Accept all')",
        "button:has-text('Accept Cookies')", "button:has-text('Accept cookies')",
        "button:has-text('I Accept')", "button:has-text('I Agree')",
        "button:has-text('Agree')", "button:has-text('Accept')",
        "button:has-text('Got it')", "button:has-text('OK')",
        "button:has-text('Dismiss')", "button:has-text('No thanks')",
        "button:has-text('Not now')",
        "[aria-label='Close']", "[aria-label='close']", "[aria-label='Dismiss']",
        "[id*='cookie'] button", "[class*='cookie-banner'] button",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=400):
                btn.click(timeout=800)
                time.sleep(0.3)
                return
        except Exception:
            pass


# ── Label resolution ──────────────────────────────────────────────────────────

def _get_label(page, el) -> str:
    """Resolve the human-readable label for a form element."""
    # aria-label
    v = (el.get_attribute("aria-label") or "").strip()
    if v:
        return v

    # aria-labelledby
    labelledby = el.get_attribute("aria-labelledby") or ""
    for ref_id in labelledby.split():
        try:
            ref = page.query_selector(f"#{ref_id}")
            if ref:
                t = ref.inner_text().strip()
                if t:
                    return t
        except Exception:
            pass

    # <label for="id">
    el_id = el.get_attribute("id") or ""
    if el_id:
        try:
            lbl = page.query_selector(f"label[for='{el_id}']")
            if lbl:
                t = lbl.inner_text().strip()
                if t:
                    return t
        except Exception:
            pass

    # placeholder or name as last resort
    return (el.get_attribute("placeholder") or el.get_attribute("name") or "").strip()


def _is_cover_letter_label(label_lower: str) -> bool:
    triggers = [
        "why are you interested", "why do you want", "tell us about yourself",
        "cover letter", "in a few sentences", "in a few words", "why this role",
        "why do you", "why would you", "why apply", "tell us why",
        "interested in this", "introduction",
    ]
    return any(t in label_lower for t in triggers)


def _is_salary_label(label_lower: str) -> bool:
    return any(t in label_lower for t in ["salary", "compensation", "pay", "wage", "expected", "desired"])


# ── Profile value lookup ──────────────────────────────────────────────────────

def _profile_value(label_lower: str, profile: dict, profile_name: str,
                   resume_name: str = "", company: str = "", title: str = "",
                   matched_keywords=None) -> Optional[str]:
    """Map a label fragment to its profile value. Returns None if no match."""
    p   = profile
    edu = p.get("education", {})

    # Name
    if any(x in label_lower for x in ["first name", "given name", "firstname"]):
        return p.get("first_name")
    if any(x in label_lower for x in ["last name", "surname", "family name", "lastname"]):
        return p.get("last_name")
    if any(x in label_lower for x in ["full name", "your name", "legal name"]):
        return p.get("full_name", f"{p.get('first_name','')} {p.get('last_name','')}")
    if label_lower.strip() == "name":
        return p.get("full_name", f"{p.get('first_name','')} {p.get('last_name','')}")

    # Contact
    if "email" in label_lower:
        return p.get("email")
    if any(x in label_lower for x in ["phone", "telephone", "mobile", "cell"]):
        return p.get("phone_formatted")
    if "linkedin" in label_lower:
        return p.get("linkedin", "")
    if "github" in label_lower:
        return p.get("github", "")
    if any(x in label_lower for x in ["website", "portfolio", "personal url", "personal site"]):
        return p.get("github", p.get("linkedin", ""))

    # Location
    if "city" in label_lower and "state" not in label_lower:
        return p.get("city")
    if "state" in label_lower and "united states" not in label_lower:
        return p.get("state")
    if any(x in label_lower for x in ["zip", "postal code", "postal"]):
        return p.get("zip")
    if "country" in label_lower:
        return p.get("country")
    if any(x in label_lower for x in ["location", "city, state", "city/state",
                                       "current location", "where are you located",
                                       "where do you live", "city and state"]):
        return f"{p.get('city','')}, {p.get('state','')}"
    if any(x in label_lower for x in ["street", "address"]):
        return f"{p.get('city','')}, {p.get('state','')} {p.get('zip','')}"

    # Education
    if any(x in label_lower for x in ["school", "university", "college", "institution"]):
        return edu.get("school", "")
    if "degree" in label_lower:
        return edu.get("degree", "")
    if any(x in label_lower for x in ["major", "field of study", "program of study", "concentration"]):
        return edu.get("major", "")
    if "gpa" in label_lower:
        return edu.get("gpa", "")
    if any(x in label_lower for x in ["graduation", "grad date", "graduation year",
                                       "expected graduation", "graduation month"]):
        return edu.get("graduation", "")

    # Work auth & sponsorship
    if any(x in label_lower for x in ["sponsorship", "require visa", "visa sponsorship",
                                       "will you require", "need sponsorship"]):
        return p.get("require_sponsorship", "No")
    if any(x in label_lower for x in ["authorized", "authorised", "legally authorized",
                                       "work in the us", "eligible to work",
                                       "right to work", "legally eligible"]):
        return p.get("authorized_to_work", "Yes")
    if "citizen" in label_lower:
        return p.get("citizenship", "US Citizen")
    if "veteran" in label_lower or "military" in label_lower:
        return p.get("veteran", "No")
    if any(x in label_lower for x in ["disability", "disabled"]):
        return p.get("disability", "No")

    # EEO fields
    if any(x in label_lower for x in ["gender", "sex"]):
        return p.get("gender", "")
    if any(x in label_lower for x in ["race", "ethnicity", "ethnic"]):
        return p.get("ethnicity", "")

    # Referral / source
    if any(x in label_lower for x in ["how did you hear", "how did you find", "referral",
                                       "where did you hear", "source", "job source",
                                       "how were you referred", "where did you learn"]):
        return "LinkedIn"

    # Salary / compensation
    if _is_salary_label(label_lower):
        return None  # handled by caller via _salary_value

    # Cover letter / open-text interest question
    if _is_cover_letter_label(label_lower):
        return get_cover_letter(title, company, resume_name, profile_name, matched_keywords)

    return None


# ── Select / radio helpers ────────────────────────────────────────────────────

def _best_option(select_el, answer: str) -> bool:
    """Select the option best matching answer. Returns True on success."""
    try:
        options  = select_el.locator("option").all()
        ans_low  = answer.lower().strip()

        # Exact
        for opt in options:
            if opt.inner_text().strip().lower() == ans_low:
                select_el.select_option(label=opt.inner_text().strip())
                return True

        # Contains (longest match wins to avoid "No" matching "None")
        best, best_len = None, 0
        for opt in options:
            t = opt.inner_text().strip()
            if ans_low in t.lower() and len(t) > best_len:
                best, best_len = t, len(t)
        if best:
            select_el.select_option(label=best)
            return True

        # Yes / No pattern
        if ans_low in ("yes", "y", "true"):
            for opt in options:
                t = opt.inner_text().strip().lower()
                if t in ("yes", "y") or (t.startswith("i am") and "not" not in t):
                    select_el.select_option(label=opt.inner_text().strip())
                    return True
        elif ans_low in ("no", "n", "false"):
            for opt in options:
                t = opt.inner_text().strip().lower()
                if t in ("no", "n") or "not" in t or "decline" in t or "do not" in t:
                    select_el.select_option(label=opt.inner_text().strip())
                    return True
    except Exception:
        pass
    return False


def _fill_radio(page, name: str, answer: str, log: list) -> bool:
    """Select the radio button in group `name` that best matches answer."""
    try:
        radios = page.locator(f"input[type='radio'][name='{name}']").all()
        ans_low = answer.lower().strip()
        for radio in radios:
            radio_id = radio.get_attribute("id") or ""
            lbl_el   = page.query_selector(f"label[for='{radio_id}']") if radio_id else None
            lbl_text = lbl_el.inner_text().strip() if lbl_el else (radio.get_attribute("value") or "")
            lbl_low  = lbl_text.lower()
            match = (
                ans_low in lbl_low
                or (ans_low == "yes" and lbl_low == "yes")
                or (ans_low == "no"  and lbl_low == "no")
                or (ans_low == "no"  and "not" in lbl_low)
            )
            if match:
                radio.click()
                log.append({"field": f"radio:{name}", "status": "filled", "value": lbl_text})
                return True
    except Exception:
        pass
    return False


# ── File upload ───────────────────────────────────────────────────────────────

def _upload_resume(page, resume_pdf_path: str, log: list) -> bool:
    selectors = [
        "input#resume",
        "input[type='file'][id*='resume']",
        "input[type='file'][name*='resume']",
        "input[type='file']",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.set_input_files(resume_pdf_path)
                human_delay(1.0, 2.0)
                log.append({"field": "resume_upload", "status": "filled",
                             "value": Path(resume_pdf_path).name})
                return True
        except Exception:
            pass
    log.append({"field": "resume_upload", "status": "skipped", "note": "no file input found"})
    return False


# ── Resume replacement (LinkedIn / Indeed) ────────────────────────────────────

def replace_linkedin_resume(page, resume_path: str, log: list) -> tuple:
    """
    Replace the stored LinkedIn resume with the job-specific PDF.
    Returns (success: bool, method: str).
    Appends _meta_resume_replaced to log for downstream logging.
    """
    for sel in [
        'input[type="file"][name*="resume"]',
        'input[type="file"][accept*="pdf"]',
        '[data-test-resume-upload-btn] input[type="file"]',
        'input[type="file"]',
    ]:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.set_input_files(resume_path)
                time.sleep(0.5)
                log.append({"field": "_meta_resume_replaced", "status": "yes",
                             "value": "file_input"})
                print(f"  Resume replaced (LinkedIn): {Path(resume_path).name}")
                return True, "file_input"
        except Exception:
            pass

    for btn_sel in [
        'button:has-text("Upload resume")', 'button:has-text("Change resume")',
        'label:has-text("Upload resume")', 'label:has-text("Change")',
        '[data-test-resume-upload-btn]',
    ]:
        try:
            btn = page.locator(btn_sel).first
            if btn.is_visible(timeout=1000):
                with page.expect_file_chooser(timeout=3000) as fc_info:
                    btn.click()
                fc_info.value.set_files(resume_path)
                time.sleep(0.5)
                log.append({"field": "_meta_resume_replaced", "status": "yes",
                             "value": "upload_button"})
                print(f"  Resume replaced (LinkedIn button): {Path(resume_path).name}")
                return True, "upload_button"
        except Exception:
            pass

    print(f"  WARNING: Could not replace LinkedIn resume — using account default")
    log.append({"field": "_meta_resume_replaced", "status": "no",
                 "value": "failed_used_default"})
    return False, "failed_used_default"


def replace_indeed_resume(page, resume_path: str, log: list) -> tuple:
    """
    Replace the stored Indeed resume with the job-specific PDF.
    Returns (success: bool, method: str).
    """
    for sel in [
        'input[type="file"][name*="resume"]',
        'input[type="file"][id*="resume"]',
        'input[type="file"][accept*="pdf"]',
        '#resume-upload-input',
        '[data-testid="resume-file-input"]',
        'input[type="file"]',
    ]:
        try:
            if page.locator(sel).count() > 0:
                page.set_input_files(sel, resume_path)
                time.sleep(0.5)
                log.append({"field": "_meta_resume_replaced", "status": "yes",
                             "value": "file_input"})
                print(f"  Resume replaced (Indeed): {Path(resume_path).name}")
                return True, "file_input"
        except Exception:
            pass

    log.append({"field": "_meta_resume_replaced", "status": "no",
                 "value": "failed_used_default"})
    return False, "failed_used_default"


# ── Universal field scanner ───────────────────────────────────────────────────

def _scan_and_fill(page, profile: dict, profile_name: str, resume_name: str,
                   log: list, company: str = "", title: str = "",
                   skip_ids: set = None):
    """
    Scan all visible inputs/textareas/selects and fill whatever matches
    the profile. skip_ids: set of element IDs already handled.
    """
    skip_ids = skip_ids or set()

    # ── Text inputs & textareas ───────────────────────────────────────────────
    elements = page.locator(
        "input:not([type='file']):not([type='hidden']):not([type='submit'])"
        ":not([type='button']):not([type='checkbox']):not([type='radio'])"
        ":not([type='image']):visible, textarea:visible"
    ).all()

    for el in elements:
        try:
            el_id = el.get_attribute("id") or ""
            if el_id in skip_ids:
                continue

            label_text  = _get_label(page, el)
            if not label_text:
                continue
            label_lower = label_text.lower()

            # Salary
            if _is_salary_label(label_lower):
                value = _salary_value(el, profile, label_lower)
                el.click(); el.fill(value); human_delay(0.2, 0.5)
                log.append({"field": label_text, "status": "filled", "value": value})
                continue

            # General lookup
            value = _profile_value(label_lower, profile, profile_name,
                                   resume_name, company, title)
            if value is None:
                log.append({"field": label_text, "status": "skipped", "note": "field not found: no match"})
                continue

            el.click(); el.fill(str(value)); human_delay(0.2, 0.5)
            log.append({"field": label_text, "status": "filled",
                        "value": str(value)[:80] + ("…" if len(str(value)) > 80 else "")})

        except Exception as e:
            try:
                lbl = _get_label(page, el)
            except Exception:
                lbl = "unknown"
            log.append({"field": lbl, "status": "error", "note": str(e)[:80]})

    # ── Selects ───────────────────────────────────────────────────────────────
    for el in page.locator("select:visible").all():
        try:
            el_id       = el.get_attribute("id") or ""
            label_text  = _get_label(page, el) or el_id
            label_lower = label_text.lower()

            if _is_salary_label(label_lower):
                value = _salary_value(el, profile, label_lower)
                ok    = _best_option(el, value)
                log.append({"field": label_text,
                             "status": "filled" if ok else "skipped",
                             "value": value if ok else "",
                             "note":  "" if ok else "no matching option"})
                continue

            # EEO by element ID keywords
            for kw, ans in [("gender",    profile.get("gender", "")),
                             ("race",      profile.get("ethnicity", "")),
                             ("ethnicity", profile.get("ethnicity", ""))]:
                if kw in el_id.lower():
                    ok = _best_option(el, ans)
                    log.append({"field": label_text,
                                 "status": "filled" if ok else "skipped",
                                 "value": ans if ok else "",
                                 "note":  "" if ok else "no matching option"})
                    break
            else:
                value = _profile_value(label_lower, profile, profile_name,
                                       resume_name, company, title)
                if value is not None:
                    ok = _best_option(el, value)
                    log.append({"field": label_text,
                                 "status": "filled" if ok else "skipped",
                                 "value": value if ok else "",
                                 "note":  "" if ok else "no matching option"})
                else:
                    log.append({"field": label_text, "status": "skipped",
                                 "note": "field not found: no match"})
        except Exception as e:
            log.append({"field": "select", "status": "error", "note": str(e)[:80]})

    # ── Checkbox / radio groups ───────────────────────────────────────────────
    seen_names: set = set()
    for el in page.locator("input[type='radio']:visible").all():
        try:
            name = el.get_attribute("name") or ""
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # Get group label via fieldset legend or nearby label
            legend = ""
            try:
                fs = el.locator("xpath=ancestor::fieldset").last
                leg_el = fs.locator("legend").first
                if leg_el:
                    legend = leg_el.inner_text().strip()
            except Exception:
                pass
            if not legend:
                legend = name.replace("_", " ")

            legend_lower = legend.lower()
            value = _profile_value(legend_lower, profile, profile_name,
                                   resume_name, company, title)
            if value is not None:
                ok = _fill_radio(page, name, value, log)
                if not ok:
                    log.append({"field": f"radio:{name}", "status": "skipped",
                                 "note": "no matching option"})
        except Exception:
            pass

    # ── Checkboxes ────────────────────────────────────────────────────────────
    for el in page.locator("input[type='checkbox']:visible").all():
        try:
            label_text  = _get_label(page, el)
            if not label_text:
                continue
            label_lower = label_text.lower()

            # Always tick agreement / consent / certification checkboxes
            if any(t in label_lower for t in [
                "agree", "terms", "privacy", "consent", "certify", "affirm",
                "acknowledge", "confirm", "accept", "authorize", "authorise",
                "above is true", "accurate", "correct", "i am", "i have read",
            ]):
                if not el.is_checked():
                    el.click()
                    human_delay(0.2, 0.4)
                log.append({"field": label_text, "status": "filled",
                             "value": "checked (agreement)"})
                continue

            value = _profile_value(label_lower, profile, profile_name,
                                   resume_name, company, title)
            if value is not None and str(value).lower() in ("yes", "true", "1"):
                if not el.is_checked():
                    el.click()
                    human_delay(0.2, 0.4)
                log.append({"field": label_text, "status": "filled", "value": "checked"})
            else:
                log.append({"field": label_text, "status": "skipped",
                             "note": "checkbox: no match"})
        except Exception as e:
            log.append({"field": "checkbox", "status": "error", "note": str(e)[:80]})


# ── Country autocomplete (Greenhouse-specific) ────────────────────────────────

def _fill_country(page, profile: dict, log: list):
    country = profile.get("country", "United States")
    el = page.query_selector("input#country")
    if not el or not el.is_visible():
        return
    try:
        el.click(); el.fill(country); human_delay(0.6, 1.0)
        suggestion = page.locator("[role='option'], [class*='suggestion'], [class*='autocomplete'] li").first
        try:
            if suggestion.is_visible(timeout=2000):
                suggestion.click()
                human_delay(0.3, 0.6)
            else:
                page.keyboard.press("Tab")
        except Exception:
            page.keyboard.press("Tab")
        log.append({"field": "country", "status": "filled", "value": country})
    except Exception as e:
        log.append({"field": "country", "status": "error", "note": str(e)[:80]})


# ── Location field fill ───────────────────────────────────────────────────────

def _fill_location(page, profile: dict, log: list):
    """
    Fill city/location fields using multiple selector strategies.
    Handles combined "Holbrook, NY", separate city+state, and zip fields.
    """
    city     = profile.get("city", "Holbrook")
    state    = profile.get("state", "NY")
    zip_code = profile.get("zip", "11741")
    combined = f"{city}, {state}"

    # Attempt combined location field first
    combined_selectors = [
        "#candidate-location",
        "#location",
        "#current_location",
        "input[name='location']",
        "input[name='candidate-location']",
        "input[placeholder*='location' i]",
        "input[placeholder*='where' i]",
        "input[aria-label*='location' i]",
        "input[aria-label*='city, state' i]",
    ]
    for sel in combined_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(); el.fill(combined); human_delay(0.3, 0.6)
                # Dismiss any autocomplete
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                log.append({"field": sel, "status": "filled", "value": combined})
                return
        except Exception:
            pass

    # Separate city field
    city_filled = False
    for sel in ["#city", "input[name='city']", "input[placeholder*='city' i]",
                "input[aria-label*='city' i]"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(); el.fill(city); human_delay(0.2, 0.4)
                log.append({"field": "city", "status": "filled", "value": city})
                city_filled = True
                break
        except Exception:
            pass

    # Separate state field
    for sel in ["#state", "input[name='state']", "select[name='state']",
                "select[id='state']", "input[placeholder*='state' i]"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                tag = el.evaluate("e => e.tagName.toUpperCase()")
                if tag == "SELECT":
                    if not _best_option(el, state):
                        _best_option(el, "New York")
                else:
                    el.click(); el.fill(state); human_delay(0.2, 0.4)
                log.append({"field": "state", "status": "filled", "value": state})
                break
        except Exception:
            pass

    # Zip field
    for sel in ["#zip", "#zipcode", "#postal", "input[name='zip']",
                "input[name='zipcode']", "input[placeholder*='zip' i]",
                "input[placeholder*='postal' i]"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(); el.fill(zip_code); human_delay(0.2, 0.4)
                log.append({"field": "zip", "status": "filled", "value": zip_code})
                break
        except Exception:
            pass

    if not city_filled:
        # Full address fallback
        for sel in ["#address", "input[name='address']", "input[placeholder*='address' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(); el.fill(f"{city}, {state} {zip_code}"); human_delay(0.2, 0.4)
                    log.append({"field": "address", "status": "filled",
                                 "value": f"{city}, {state} {zip_code}"})
                    break
            except Exception:
                pass


# ── Page-ready helper ────────────────────────────────────────────────────────

def wait_for_page_ready(page, timeout: int = 15000) -> None:
    """Wait for networkidle, loading spinners to vanish, and JS to finish rendering."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    for sel in [".loading", ".spinner", "[class*='loading']",
                "[class*='skeleton']", "[aria-busy='true']"]:
        try:
            page.locator(sel).first.wait_for(state="hidden", timeout=2000)
        except Exception:
            pass
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass


# ── Platform-specific apply button finders ───────────────────────────────────

def find_linkedin_apply_button(page):
    """
    Try every known LinkedIn apply button selector.
    Returns (element, 'easy_apply'|'external_apply') or (None, None).
    """
    easy_apply_selectors = [
        "button[aria-label*='Easy Apply']",
        "button[aria-label*='easy apply' i]",
        "button[data-control-name='jobdetails_topcard_inapply']",
        "button[data-job-id]",
        ".jobs-apply-button",
        ".jobs-apply-button--top-card",
        "button.jobs-apply-button",
        "button[class*='jobs-apply-button']",
        ".jobs-s-apply button",
        ".jobs-s-apply--top-card button",
        "[class*='apply'] button",
        ".job-details-jobs-unified-top-card__container--two-pane button",
        ".jobs-unified-top-card__content--two-pane button",
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        ".jobs-details__main-content button",
        ".jobs-search__job-details--wrapper button",
        "main button",
    ]
    for sel in easy_apply_selectors:
        try:
            for el in page.locator(sel).all():
                try:
                    if el.is_visible(timeout=1000):
                        text = el.inner_text().strip().lower()
                        if any(w in text for w in ["easy apply", "apply now", "apply"]):
                            print(f"  [BTN] LinkedIn Easy Apply: {sel}")
                            return el, "easy_apply"
                except Exception:
                    continue
        except Exception:
            continue

    external_selectors = [
        "a:has-text('Apply on company site')",
        "a:has-text('Apply on company website')",
        "a:has-text('Apply at')",
        "a:has-text('Apply externally')",
        "button:has-text('Apply on company site')",
        "button:has-text('Apply on company website')",
        "button:has-text('Apply externally')",
        ".jobs-apply-button a",
        "[data-tracking-control-name*='apply'] a",
        "a[href*='apply']",
    ]
    for sel in external_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                print(f"  [BTN] LinkedIn External Apply: {sel}")
                return el, "external_apply"
        except Exception:
            continue

    # Scroll to top and retry with role-based search
    try:
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
        for text in ["Easy Apply", "Apply now", "Apply on company site"]:
            try:
                el = page.get_by_role("button", name=text, exact=False).first
                if el.is_visible(timeout=1000):
                    btn_type = "easy_apply" if "easy" in text.lower() else "external_apply"
                    print(f"  [BTN] LinkedIn role-search: '{text}'")
                    return el, btn_type
            except Exception:
                continue
    except Exception:
        pass

    return None, None


def find_indeed_apply_button(page):
    """Try all Indeed apply button patterns. Returns (element, button_type) or (None, None)."""
    selectors = [
        "button[id='indeedApplyButton']",
        "button.ia-continueButton",
        "[data-testid='apply-button']",
        "[class*='apply-button']",
        ".jobsearch-IndeedApplyButton-newDesign button",
        ".jobsearch-IndeedApplyButton button",
        "button:has-text('Apply now')",
        "button:has-text('Easily apply')",
        "button:has-text('Apply on company site')",
        "a:has-text('Apply on company site')",
        "a[href*='/apply/']",
        "a[href*='apply?']",
        "[aria-label*='apply' i]",
        "main button[type='button']",
        ".jobsearch-ViewJobLayout button",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                text = el.inner_text().strip().lower()
                if any(w in text for w in ["apply", "continue"]):
                    is_ext = "company site" in text or "externally" in text
                    btn_type = "external_apply" if is_ext else "easy_apply"
                    print(f"  [BTN] Indeed {btn_type}: {sel}")
                    return el, btn_type
        except Exception:
            continue
    return None, None


def find_greenhouse_apply_button(page):
    """Try all Greenhouse apply button patterns. Returns (element, 'direct_form') or (None, None)."""
    for sel in ["#apply_button", "a#apply_button",
                "a:has-text('Apply for this job')", "button:has-text('Apply for this job')",
                "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                "a:has-text('Apply')", ".apply-button", "[class*='apply']", "a[href*='/apply']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                return el, "direct_form"
        except Exception:
            continue
    return None, None


def find_lever_apply_button(page):
    """Try all Lever apply button patterns. Returns (element, 'direct_form') or (None, None)."""
    for sel in ["a.postings-btn", "a:has-text('Apply for this job')",
                ".posting-apply a", ".template-btn-submit",
                "a:has-text('Apply')", "button:has-text('Apply')", "[class*='apply']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                return el, "direct_form"
        except Exception:
            continue
    return None, None


def find_workday_apply_button(page):
    """Try all Workday apply button patterns. Returns (element, 'direct_form') or (None, None)."""
    for sel in ["a[data-automation-id='applyNowButton']",
                "button[data-automation-id='applyNowButton']",
                "[data-automation-id*='apply']", "button:has-text('Apply')",
                "a:has-text('Apply')", "[class*='apply-button']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                return el, "direct_form"
        except Exception:
            continue
    return None, None


def find_apply_button_generic(page):
    """Last-resort detector: scans entire page for any apply button."""
    for name_pat in ["Easy Apply", "Apply Now", "Apply for this job",
                     "Apply on company site", "Apply", "Submit Application"]:
        for role in ("button", "link"):
            try:
                el = page.get_by_role(role, name=name_pat, exact=False).first
                if el.is_visible(timeout=1000):
                    is_ext = "company site" in name_pat.lower()
                    btn_type = "external_apply" if is_ext else "direct_form"
                    print(f"  [BTN] Generic role='{role}' name='{name_pat}'")
                    return el, btn_type
            except Exception:
                continue
    try:
        for btn in page.get_by_role("button").all()[:30]:
            try:
                if btn.is_visible(timeout=500):
                    text = (btn.inner_text() + " " +
                            (btn.get_attribute("aria-label") or "")).lower()
                    if "apply" in text:
                        print(f"  [BTN] Generic text-scan: '{text[:40]}'")
                        return btn, "direct_form"
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def find_apply_button(page, platform: str, context=None):
    """
    Master apply-button finder: platform-specific first, then generic fallback.
    Saves a full-page debug screenshot before returning (None, None).
    """
    from datetime import datetime as _dt
    _finders = {
        "linkedin":   find_linkedin_apply_button,
        "indeed":     find_indeed_apply_button,
        "greenhouse": find_greenhouse_apply_button,
        "lever":      find_lever_apply_button,
        "workday":    find_workday_apply_button,
    }
    print(f"  [BTN] Searching for apply button on {platform}...")
    if platform in _finders:
        el, bt = _finders[platform](page)
        if el:
            return el, bt
        print(f"  [BTN] Platform handler found nothing — trying generic fallback")

    el, bt = find_apply_button_generic(page)
    if el:
        return el, bt

    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    scr_dir = Path(__file__).parent / "output" / "screenshots"
    scr_dir.mkdir(parents=True, exist_ok=True)
    scr_path = scr_dir / f"debug_no_button_{platform}_{ts}.png"
    try:
        page.screenshot(path=str(scr_path), full_page=True)
        print(f"  [BTN] No apply button found after all strategies. "
              f"Debug screenshot: {scr_path.name}")
    except Exception as e:
        print(f"  [BTN] No apply button found. Screenshot failed: {e}")
    return None, None


# ── Indeed Easy Apply handler ─────────────────────────────────────────────────

def fill_indeed_easy_apply(page, context, profile: dict, profile_name: str,
                            resume_pdf_path: str, log: list,
                            company: str = "", title: str = "") -> str:
    """
    Handle all three Indeed scenarios.
    Returns: 'easy_apply' | 'company_site' | 'no_button'
    Page object may change (new tab) — caller must use context.pages[-1] after.
    """
    human_delay(1.5, 2.5)
    resume_name = Path(resume_pdf_path).name

    wait_for_page_ready(page)
    btn, btn_type = find_indeed_apply_button(page)

    if btn is None:
        return "no_button"

    if btn_type == "external_apply":
        pages_before = len(context.pages)
        try:
            btn.scroll_into_view_if_needed(timeout=2000)
            btn.click()
            human_delay(2, 3)
            if len(context.pages) > pages_before:
                new_page = context.pages[-1]
                try:
                    new_page.wait_for_load_state("domcontentloaded", timeout=30000)
                except Exception:
                    pass
                human_delay(1.5, 2.5)
                log.append({"field": "indeed_apply_mode", "status": "filled",
                             "value": "company_site → new tab"})
                return "company_site"
        except Exception:
            pass
        return "no_button"

    # easy_apply: click and navigate the multi-step modal
    try:
        btn.scroll_into_view_if_needed(timeout=2000)
        btn.click()
        human_delay(1.5, 2.5)
    except Exception:
        return "no_button"

    try:
        page.wait_for_selector(
            "[aria-label='Apply to job'], .ia-BasePage, "
            "[data-testid='ia-view-root'], .ia-Questions",
            timeout=5000,
        )
    except Exception:
        pass

    for _step in range(20):
        if detect_recaptcha(page):
            print("\n  [CAPTCHA] Solve reCAPTCHA then press Enter...")
            input("  > ")

        try:
            fi = page.locator("input[type='file']").first
            if fi.is_visible(timeout=1000):
                replace_indeed_resume(page, resume_pdf_path, log)
                human_delay(1, 2)
        except Exception:
            pass

        _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)

        try:
            sub = page.locator(
                "button:has-text('Submit your application'), "
                "button:has-text('Submit application')"
            ).first
            if sub.is_visible(timeout=1000):
                return "easy_apply"
        except Exception:
            pass

        advanced = False
        for next_text in ["Continue", "Next", "Review your application",
                          "Review", "Next: Work experience"]:
            try:
                nav = page.locator(f"button:has-text('{next_text}')").last
                if nav.is_visible(timeout=1000):
                    nav.click()
                    try:
                        page.wait_for_selector(
                            ".ia-BasePage, [data-testid='ia-view-root'],"
                            " .ia-Questions, [class*='ia-']",
                            timeout=5000,
                        )
                    except Exception:
                        pass
                    human_delay(1, 2)
                    advanced = True
                    break
            except Exception:
                pass
        if not advanced:
            break
    return "easy_apply"


# ── LinkedIn apply handler ────────────────────────────────────────────────────

def handle_linkedin_apply(page, context, profile: dict, profile_name: str,
                           resume_pdf_path: str, log: list,
                           company: str = "", title: str = "") -> tuple:
    """
    Handle a LinkedIn job page apply flow.
    Returns (method, redirect_page):
      ("easy_apply", page)       — Easy Apply modal navigated to submit step
      ("company_site", new_page) — Apply redirected to company site
      ("no_button", None)        — no apply button found after exhaustive search
    """
    human_delay(1.5, 2.5)
    resume_name = Path(resume_pdf_path).name

    wait_for_page_ready(page)

    # Check if already applied
    try:
        if page.locator("text=Applied").is_visible(timeout=2000):
            print("  [LinkedIn] Already applied to this job")
            return "no_button", None
    except Exception:
        pass

    btn, btn_type = find_linkedin_apply_button(page)

    if btn is None:
        return "no_button", None

    if btn_type == "easy_apply":
        try:
            btn.scroll_into_view_if_needed(timeout=2000)
            btn.click()
        except Exception:
            return "no_button", None

        try:
            page.wait_for_selector(
                ".jobs-easy-apply-modal, [data-test-modal], [role='dialog']",
                timeout=10000,
            )
        except Exception:
            pass
        human_delay(1, 1.5)

        for _step in range(15):
            if detect_recaptcha(page):
                print("\n  [CAPTCHA] reCAPTCHA — solve then press Enter...")
                input("  > ")

            try:
                fi = page.locator("input[type='file']").first
                if fi.is_visible(timeout=500):
                    replace_linkedin_resume(page, resume_pdf_path, log)
                    human_delay(1, 2)
            except Exception:
                pass

            _scan_and_fill(page, profile, profile_name, resume_name,
                           log, company, title)

            # Submit button visible → final step reached
            try:
                sub = page.locator(
                    "button:has-text('Submit application'), "
                    "button:has-text('Submit Application')"
                ).first
                if sub.is_visible(timeout=500):
                    print("  [LinkedIn] Reached submit step")
                    return "easy_apply", page
            except Exception:
                pass

            # Advance to next step
            advanced = False
            for btn_text in ["Next", "Continue", "Review"]:
                try:
                    nav = page.locator(f"button:has-text('{btn_text}')").last
                    if nav.is_visible(timeout=1000):
                        nav.click()
                        try:
                            page.wait_for_load_state("networkidle", timeout=4000)
                        except Exception:
                            pass
                        human_delay(1, 1.5)
                        advanced = True
                        break
                except Exception:
                    pass
            if not advanced:
                try:
                    sub = page.locator(
                        "button:has-text('Submit application'), "
                        "button:has-text('Submit Application')"
                    ).first
                    if sub.is_visible(timeout=1000):
                        return "easy_apply", page
                except Exception:
                    pass
                break

        return "easy_apply", page

    else:  # external_apply
        pages_before = len(context.pages)
        url_before   = page.url
        try:
            btn.scroll_into_view_if_needed(timeout=2000)
            btn.click()
            human_delay(2, 3)
        except Exception:
            return "no_button", None

        if len(context.pages) > pages_before:
            new_page = context.pages[-1]
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            human_delay(1.5, 2.5)
            log.append({"field": "linkedin_apply_mode", "status": "filled",
                        "value": "company_site → new tab"})
            return "company_site", new_page

        if page.url != url_before:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            log.append({"field": "linkedin_apply_mode", "status": "filled",
                        "value": "company_site → same tab"})
            return "company_site", page

        return "no_button", None


# ── Submit helpers ────────────────────────────────────────────────────────────

def find_submit_button(page, platform: str):
    """Return the submit button locator, or None. Tries platform-specific selectors first."""
    platform_map = {
        "greenhouse":      ["[data-qa='btn-submit']", "[data-qa='submit-app-btn']",
                            "button#submit_app", "button:has-text('Submit Application')"],
        "lever":           [".template-btn-submit", "button[type='submit'].postings-btn",
                            "a.template-btn-submit", "button:has-text('Submit Application')"],
        "workday":         ["button[data-automation-id='bottomNavigationNextButton']",
                            "button[data-automation-id*='submit']",
                            "button[aria-label*='Submit']",
                            "button:has-text('Submit')"],
        "ashby":           ["button[type='submit']", "button:has-text('Submit Application')",
                            "button[class*='ashby']:has-text('Submit')"],
        "icims":           ["input.iCIMS_Button[value*='Submit']", "button.iCIMS_Button",
                            ".iCIMS_FormElement input[type='submit']"],
        "taleo":           ["input[type='submit'][value*='Submit']",
                            "button[class*='submit']", "a.btn:has-text('Submit')"],
        "smartrecruiters": ["button[data-label='Submit Application']",
                            "[data-testid='btn-apply']",
                            "button.wui-btn--primary:has-text('Submit')"],
        "linkedin":        ["button:has-text('Submit application')",
                            "button:has-text('Submit Application')"],
        "indeed":          ["button:has-text('Submit your application')",
                            "button:has-text('Submit application')",
                            "button:has-text('Submit')"],
    }
    for sel in platform_map.get(platform, []):
        try:
            el = page.locator(sel).last
            if el.is_visible():
                return el
        except Exception:
            pass

    # Universal fallback — ordered most to least specific
    universal = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit Application')",
        "button:has-text('Submit application')",
        "button:has-text('Submit your application')",
        "button:has-text('Submit')",
        "button:has-text('Complete Application')",
        "button:has-text('Send Application')",
        "button:has-text('Apply Now')",
        "button:has-text('Apply now')",
        "[data-qa='btn-submit']",
        "[data-automation-id*='submit']",
        "[class*='submit-btn']",
        "[class*='btn-submit']",
        "button[class*='primary']:has-text('Apply')",
        "button[class*='primary']:has-text('Submit')",
        "a[class*='button']:has-text('Submit')",
        "a[class*='button']:has-text('Apply')",
    ]
    for sel in universal:
        try:
            el = page.locator(sel).last
            if el.is_visible():
                return el
        except Exception:
            pass
    return None


CONFIRMATION_KEYWORDS = [
    "thank you", "application submitted", "successfully submitted",
    "received your application", "application received",
    "we'll be in touch", "we will be in touch", "application complete",
    "you've applied", "you have applied", "application sent",
    "your application has been", "successfully applied",
    "application confirmed", "we received your",
    "your application was sent",        # LinkedIn Easy Apply
    "application was submitted",
]


def click_submit(page, platform: str) -> bool:
    """Click the submit button. Retries once on stale element or transient failure."""
    for attempt in range(2):
        btn = find_submit_button(page, platform)
        if not btn:
            if attempt == 0:
                human_delay(1.5, 2.5)  # wait for dynamic rendering then retry
                continue
            return False
        try:
            btn.scroll_into_view_if_needed()
            human_delay(0.5, 1.0)
            btn.click()
            human_delay(1.5, 2.0)
            return True
        except Exception as e:
            if attempt == 0:
                print(f"  [WARN] Submit click attempt 1 failed ({e}), retrying...")
                human_delay(2, 3)
            else:
                print(f"  [ERROR] Submit click failed after retry: {e}")
                return False
    return False


def wait_for_submission_confirmation(page, baseline_url: str,
                                     timeout_s: int = 10) -> tuple[str, str]:
    """
    Poll up to timeout_s seconds for evidence of a successful submission.

    Returns (status, detail) where status is one of:
      'confirmed'   — URL changed AND/OR confirmation keyword found
      'url_changed' — URL changed but no keyword (probably still submitted)
      'stuck'       — no change after timeout (form still visible)
    """
    import time as _time
    deadline = _time.time() + timeout_s
    base     = baseline_url.rstrip("/")

    while _time.time() < deadline:
        try:
            current = page.url.rstrip("/")
            try:
                body = page.inner_text("body").lower()[:3000]
            except Exception:
                body = ""

            url_changed   = current != base
            kw_found      = any(kw in body for kw in CONFIRMATION_KEYWORDS)

            if url_changed and kw_found:
                return "confirmed", "URL changed + confirmation keyword"
            if kw_found:
                kw = next(kw for kw in CONFIRMATION_KEYWORDS if kw in body)
                return "confirmed", f"keyword: '{kw}'"
            if url_changed:
                return "url_changed", f"→ {current[:80]}"
        except Exception:
            pass
        _time.sleep(0.5)

    return "stuck", "no confirmation after 10s"


# ── Greenhouse full fill ──────────────────────────────────────────────────────

def _fill_greenhouse(page, profile: dict, profile_name: str,
                     resume_pdf_path: str, log: list,
                     company: str = "", title: str = ""):
    human_delay(1.5, 2.5)
    resume_name = Path(resume_pdf_path).name

    # Known Greenhouse field IDs — fill first for reliability
    known = {
        "first_name":         profile.get("first_name", ""),
        "last_name":          profile.get("last_name", ""),
        "email":              profile.get("email", ""),
        "phone":              profile.get("phone_formatted", ""),
        "candidate-location": f"{profile.get('city','')}, {profile.get('state','')}",
    }
    filled_ids = set()
    for field_id, value in known.items():
        if not value:
            continue
        try:
            el = page.query_selector(f"input#{field_id}")
            if el and el.is_visible():
                el.click(); el.fill(value); human_delay(0.25, 0.5)
                log.append({"field": field_id, "status": "filled", "value": value})
                filled_ids.add(field_id)
        except Exception as e:
            log.append({"field": field_id, "status": "error", "note": str(e)[:80]})

    # Country autocomplete
    _fill_country(page, profile, log)
    filled_ids.add("country")

    # Location field (city/state/zip or combined)
    _fill_location(page, profile, log)
    for loc_id in ("city", "location", "candidate-location", "address",
                   "current_location", "zip", "zipcode", "postal", "state"):
        filled_ids.add(loc_id)

    # Resume upload
    _upload_resume(page, resume_pdf_path, log)

    # Universal scanner for all remaining fields (custom questions, EEO, etc.)
    _scan_and_fill(page, profile, profile_name, resume_name, log,
                   company, title, skip_ids=filled_ids)

    human_delay(0.5, 1.0)


# ── LinkedIn Easy Apply ───────────────────────────────────────────────────────

def _fill_linkedin(page, profile: dict, profile_name: str,
                   resume_pdf_path: str, log: list,
                   company: str = "", title: str = "") -> bool:
    """
    Handle LinkedIn Easy Apply multi-step modal.
    Returns True when the final Review page is reached.
    """
    human_delay(1, 2)
    resume_name = Path(resume_pdf_path).name

    # Open modal
    try:
        btn = page.locator("button:has-text('Easy Apply')").first
        if btn.is_visible():
            btn.click()
            page.wait_for_selector(
                ".jobs-easy-apply-modal, [data-test-modal], [role='dialog']",
                timeout=10000,
            )
            human_delay(1, 1.5)
        else:
            log.append({"field": "easy_apply_btn", "status": "skipped", "note": "not visible"})
            return False
    except Exception as e:
        log.append({"field": "easy_apply_btn", "status": "error", "note": str(e)[:80]})
        return False

    for _step in range(15):
        if detect_recaptcha(page):
            print("\n  [CAPTCHA] reCAPTCHA detected — solve it in the browser, then press Enter...")
            input("  > ")

        # Replace resume on this step
        try:
            fi = page.locator("input[type='file']").first
            if fi.is_visible():
                replace_linkedin_resume(page, resume_pdf_path, log)
                human_delay(1, 2)
        except Exception:
            pass

        # Fill visible fields on this step
        _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)

        # Check for final review / submit step
        try:
            if page.locator(
                "button:has-text('Submit application'), button:has-text('Submit Application')"
            ).is_visible():
                return True
        except Exception:
            pass

        # Advance to next step
        advanced = False
        for btn_text in ["Next", "Continue", "Review"]:
            try:
                nav_btn = page.locator(f"button:has-text('{btn_text}')").last
                if nav_btn.is_visible():
                    nav_btn.click()
                    human_delay(1, 2)
                    advanced = True
                    break
            except Exception:
                pass
        if not advanced:
            break

    return False


# ── Workday handler ───────────────────────────────────────────────────────────

def _fill_workday(page, profile: dict, profile_name: str,
                  resume_pdf_path: str, log: list,
                  company: str = "", title: str = ""):
    """Fill Workday multi-step application wizard."""
    human_delay(1.5, 2.5)
    resume_name = Path(resume_pdf_path).name

    for _step in range(12):
        dismiss_popups(page)

        # Upload resume/CV when a file input appears on this step
        try:
            for fi in page.locator("input[type='file']").all():
                if fi.is_visible(timeout=500):
                    fi.set_input_files(resume_pdf_path)
                    time.sleep(1.5)
                    log.append({"field": "_meta_resume_replaced", "status": "yes",
                                "value": "workday_file_input"})
                    break
        except Exception:
            pass

        _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)

        # Stop if submit button is the only navigation left
        for sub_sel in [
            "button[data-automation-id='bottomNavigationNextButton']",
            "button[aria-label*='Submit']", "button:has-text('Submit')",
        ]:
            try:
                sub = page.locator(sub_sel).last
                if sub.is_visible(timeout=400):
                    label = (sub.inner_text() or "").strip().lower()
                    if any(t in label for t in ["submit", "done", "complete", "finish"]):
                        return  # caller (_finish_job) will click
            except Exception:
                pass

        # Advance to next step
        advanced = False
        for sel in [
            "button[data-automation-id='bottomNavigationNextButton']",
            "button:has-text('Next')", "button:has-text('Save and Continue')",
            "button:has-text('Continue')", "button:has-text('Save')",
        ]:
            try:
                btn = page.locator(sel).last
                if btn.is_visible(timeout=1000):
                    label = (btn.inner_text() or "").strip().lower()
                    if any(t in label for t in ["submit", "done", "complete", "finish"]):
                        return  # reached final step — let caller submit
                    btn.click()
                    human_delay(2.5, 4.0)  # Workday transitions are slow
                    advanced = True
                    break
            except Exception:
                pass
        if not advanced:
            break


# ── Lever handler ─────────────────────────────────────────────────────────────

def _fill_lever(page, profile: dict, profile_name: str,
                resume_pdf_path: str, log: list,
                company: str = "", title: str = ""):
    """Fill Lever single-page application form."""
    human_delay(1, 2)
    resume_name = Path(resume_pdf_path).name
    _upload_resume(page, resume_pdf_path, log)
    _fill_location(page, profile, log)
    _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)


# ── Ashby handler ─────────────────────────────────────────────────────────────

def _fill_ashby(page, profile: dict, profile_name: str,
                resume_pdf_path: str, log: list,
                company: str = "", title: str = ""):
    """Fill Ashby ATS application form."""
    human_delay(1, 2)
    resume_name = Path(resume_pdf_path).name
    _upload_resume(page, resume_pdf_path, log)
    _fill_location(page, profile, log)
    _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)


# ── iCIMS handler ─────────────────────────────────────────────────────────────

def _fill_icims(page, profile: dict, profile_name: str,
                resume_pdf_path: str, log: list,
                company: str = "", title: str = ""):
    """Fill iCIMS multi-page application."""
    human_delay(1, 2)
    resume_name = Path(resume_pdf_path).name

    for _step in range(8):
        _upload_resume(page, resume_pdf_path, log)
        _fill_location(page, profile, log)
        _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)

        advanced = False
        for sel in ["button:has-text('Next')", "button:has-text('Continue')",
                    "input[type='button'][value*='Next']"]:
            try:
                btn = page.locator(sel).last
                if btn.is_visible(timeout=1000):
                    label = (btn.get_attribute("value") or btn.inner_text() or "").lower()
                    if any(t in label for t in ["submit", "complete"]):
                        return
                    btn.click()
                    human_delay(2, 3)
                    advanced = True
                    break
            except Exception:
                pass
        if not advanced:
            break


# ── Generic handler ───────────────────────────────────────────────────────────

def _fill_generic(page, profile: dict, profile_name: str,
                  resume_pdf_path: str, log: list,
                  company: str = "", title: str = ""):
    human_delay(1, 2)
    resume_name = Path(resume_pdf_path).name
    _fill_location(page, profile, log)
    _upload_resume(page, resume_pdf_path, log)
    _scan_and_fill(page, profile, profile_name, resume_name, log, company, title)


# ── Public API ────────────────────────────────────────────────────────────────

def fill_form(page, platform: str, profile: dict, profile_name: str,
              resume_pdf_path: str, company: str = "", title: str = "",
              context=None) -> list:
    """
    Fill the application form for the detected platform.
    Returns a list of log dicts: {field, status, value?, note?}
    """
    log = []

    if detect_recaptcha(page):
        print("\n  [CAPTCHA] reCAPTCHA detected — solve it in the browser, then press Enter...")
        input("  > ")

    if platform == "greenhouse":
        _fill_greenhouse(page, profile, profile_name, resume_pdf_path, log, company, title)
    elif platform == "workday":
        _fill_workday(page, profile, profile_name, resume_pdf_path, log, company, title)
    elif platform == "lever":
        _fill_lever(page, profile, profile_name, resume_pdf_path, log, company, title)
    elif platform == "ashby":
        _fill_ashby(page, profile, profile_name, resume_pdf_path, log, company, title)
    elif platform == "icims":
        _fill_icims(page, profile, profile_name, resume_pdf_path, log, company, title)
    elif platform == "linkedin":
        # Fallback only — primary LinkedIn path goes through handle_linkedin_apply()
        _fill_linkedin(page, profile, profile_name, resume_pdf_path, log, company, title)
    else:
        _fill_generic(page, profile, profile_name, resume_pdf_path, log, company, title)

    return log
