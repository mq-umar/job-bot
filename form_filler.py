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
    if "greenhouse.io" in url:  return "greenhouse"
    if "lever.co"      in url:  return "lever"
    if "workday"       in url:  return "workday"
    if "linkedin.com"  in url:  return "linkedin"
    if "indeed.com"    in url:  return "indeed"
    if "taleo"         in url:  return "taleo"
    return "generic"


# ── Job description extraction ────────────────────────────────────────────────

def extract_job_description(page, platform: str) -> str:
    selectors = {
        "greenhouse": ["#content", ".job-post__description", "[data-qa='job-description']", "section.content"],
        "lever":      [".posting-requirements", ".section-wrapper", "[class*='description']"],
        "indeed":     ["#jobDescriptionText", ".jobsearch-jobDescriptionText"],
        "linkedin":   [".jobs-description__content", ".jobs-box__html-content"],
        "generic":    ["[class*='description']", "[class*='job-details']", "main", "article", "#content"],
    }
    for sel in selectors.get(platform, selectors["generic"]):
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                if len(text) > 200:
                    return text.strip()
        except Exception:
            pass
    try:
        return page.inner_text("body")[:12000]
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

    # Scenario A: Easy Apply / Apply now button opens a modal
    for btn_text in ["Apply now", "Easy Apply", "Apply Now"]:
        try:
            btn = page.locator(f"button:has-text('{btn_text}'), a:has-text('{btn_text}')").first
            if btn.is_visible(timeout=2000):
                btn.click()
                human_delay(1.5, 2.5)
                # Check if modal opened (Indeed Easy Apply)
                try:
                    page.wait_for_selector(
                        "[aria-label='Apply to job'], .ia-BasePage, "
                        "[data-testid='ia-view-root'], .ia-Questions",
                        timeout=5000,
                    )
                    # Multi-step modal — iterate up to 20 steps
                    for _step in range(20):
                        if detect_recaptcha(page):
                            print("\n  [CAPTCHA] Solve reCAPTCHA then press Enter...")
                            input("  > ")

                        # Upload resume if file input visible
                        try:
                            fi = page.locator("input[type='file']").first
                            if fi.is_visible(timeout=1000):
                                fi.set_input_files(resume_pdf_path)
                                human_delay(1, 2)
                                log.append({"field": "resume_upload", "status": "filled",
                                             "value": resume_name})
                        except Exception:
                            pass

                        _scan_and_fill(page, profile, profile_name, resume_name,
                                       log, company, title)

                        # Submit button = final step reached
                        try:
                            sub = page.locator(
                                "button:has-text('Submit your application'), "
                                "button:has-text('Submit application')"
                            ).first
                            if sub.is_visible(timeout=1000):
                                return "easy_apply"
                        except Exception:
                            pass

                        # Advance step
                        advanced = False
                        for next_text in ["Continue", "Next", "Review your application",
                                          "Review", "Next: Work experience"]:
                            try:
                                nav = page.locator(f"button:has-text('{next_text}')").last
                                if nav.is_visible(timeout=1000):
                                    nav.click()
                                    human_delay(1.5, 2.5)
                                    advanced = True
                                    break
                            except Exception:
                                pass
                        if not advanced:
                            break
                    return "easy_apply"
                except Exception:
                    pass  # No modal — might have redirected or opened company site
        except Exception:
            pass

    # Scenario B: Apply on company site → opens new tab
    for sel_text in ["Apply on company site", "Apply on Company Site"]:
        try:
            btn = page.locator(
                f"button:has-text('{sel_text}'), a:has-text('{sel_text}')"
            ).first
            if btn.is_visible(timeout=2000):
                pages_before = len(context.pages)
                btn.click()
                human_delay(2, 3)
                if len(context.pages) > pages_before:
                    new_page = context.pages[-1]
                    new_page.wait_for_load_state("domcontentloaded", timeout=30000)
                    human_delay(1.5, 2.5)
                    log.append({"field": "indeed_apply_mode", "status": "filled",
                                 "value": "company_site → new tab"})
                    return "company_site"
        except Exception:
            pass

    return "no_button"


# ── Submit helpers ────────────────────────────────────────────────────────────

def find_submit_button(page, platform: str):
    """Return the submit button locator, or None."""
    candidates = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit Application')",
        "button:has-text('Submit application')",
        "button:has-text('Submit')",
        "[data-qa='btn-submit']",
        "button:has-text('Apply')",
    ]
    for sel in candidates:
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
]


def click_submit(page, platform: str) -> bool:
    """Click the submit button. Returns True if button was found and clicked."""
    btn = find_submit_button(page, platform)
    if not btn:
        return False
    try:
        btn.scroll_into_view_if_needed()
        human_delay(0.5, 1.0)
        btn.click()
        human_delay(1.0, 1.5)  # short wait — caller does confirmation check
        return True
    except Exception as e:
        print(f"  [ERROR] Submit click failed: {e}")
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

        # Upload resume if step has file input
        try:
            fi = page.locator("input[type='file']").first
            if fi.is_visible():
                fi.set_input_files(resume_pdf_path)
                human_delay(1, 2)
                log.append({"field": "resume_upload", "status": "filled",
                             "value": resume_name})
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
    elif platform == "linkedin":
        _fill_linkedin(page, profile, profile_name, resume_pdf_path, log, company, title)
    else:
        _fill_generic(page, profile, profile_name, resume_pdf_path, log, company, title)

    return log
