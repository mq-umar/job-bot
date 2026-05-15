"""
form_filler.py
Playwright-based form filling for major ATS platforms.
Handles JD extraction, field mapping, and file upload.
"""
import random
import time


# ── Human simulation ──────────────────────────────────────────────────────────

def human_delay(min_s: float = 0.5, max_s: float = 1.5):
    time.sleep(random.uniform(min_s, max_s))


def human_type(page, selector: str, text: str):
    page.click(selector)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.03, 0.10))


# ── Platform detection ────────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    url = url.lower()
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    if "workday" in url:
        return "workday"
    if "linkedin.com" in url:
        return "linkedin"
    if "indeed.com" in url:
        return "indeed"
    if "taleo" in url:
        return "taleo"
    return "generic"


# ── Job description extraction ────────────────────────────────────────────────

def extract_job_description(page, platform: str) -> str:
    """Extract full job description text from current page."""
    selectors = {
        "greenhouse": [
            "#content",
            ".job-post__description",
            "[data-qa='job-description']",
            ".content-intro",
            "section.content",
        ],
        "lever": [
            ".posting-requirements",
            ".section-wrapper",
            "[class*='description']",
        ],
        "indeed": [
            "#jobDescriptionText",
            ".jobsearch-jobDescriptionText",
            "[data-testid='jobsearch-JobComponent-description']",
        ],
        "linkedin": [
            ".jobs-description__content",
            ".jobs-box__html-content",
            "[class*='description']",
        ],
        "generic": [
            "[class*='description']",
            "[class*='job-details']",
            "main",
            "article",
            "#content",
        ],
    }

    candidates = selectors.get(platform, selectors["generic"])
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                if len(text) > 200:
                    return text.strip()
        except Exception:
            pass

    # Fallback: grab all visible text from body
    try:
        return page.inner_text("body")[:10000]
    except Exception:
        return ""


# ── Greenhouse handler ────────────────────────────────────────────────────────

def _safe_fill(page, selector: str, value: str):
    """Try to fill a field; silently skip if not found."""
    try:
        el = page.query_selector(selector)
        if el and el.is_visible():
            el.click()
            el.fill(value)
            human_delay(0.2, 0.5)
    except Exception:
        pass


def _fill_by_label(page, label_text: str, value: str):
    """Find an input associated with a label containing label_text."""
    try:
        label = page.get_by_text(label_text, exact=False).first
        if not label:
            return
        for_id = label.get_attribute("for")
        if for_id:
            page.fill(f"#{for_id}", value)
            return
        parent = label.locator("..")
        inp = parent.locator("input, textarea").first
        if inp:
            inp.fill(value)
    except Exception:
        pass


def _fill_question_by_label(page, label_fragment: str, value: str):
    """
    Fill a Greenhouse custom question input by searching all labels for
    a fragment match, then filling the associated input by for= id.
    """
    try:
        labels = page.locator("label").all()
        for label in labels:
            text = label.inner_text()
            if label_fragment.lower() in text.lower():
                for_id = label.get_attribute("for")
                if for_id:
                    el = page.query_selector(f"#{for_id}")
                    if el and el.is_visible():
                        tag = el.evaluate("el => el.tagName.toLowerCase()")
                        if tag in ("input", "textarea"):
                            el.fill(value)
                            human_delay(0.2, 0.5)
                        elif tag == "select":
                            options = el.locator("option").all()
                            for opt in options:
                                if value.lower() in opt.inner_text().lower():
                                    el.select_option(label=opt.inner_text())
                                    break
                        return
    except Exception:
        pass


def fill_greenhouse(page, profile: dict, resume_pdf_path: str,
                    interest_blurb: str = ""):
    """
    Fill a Greenhouse application form.
    On many Greenhouse postings the form is embedded on the job description page
    (no separate Apply navigation needed).
    interest_blurb: optional answer to 'why interested' custom question.
    """
    human_delay(1.5, 2.5)

    # Core identity fields — Greenhouse uses predictable IDs
    _safe_fill(page, "input#first_name", profile["first_name"])
    _safe_fill(page, "input#last_name",  profile["last_name"])
    _safe_fill(page, "input#email",      profile["email"])
    _safe_fill(page, "input#phone",      profile["phone_formatted"])

    human_delay(0.4, 0.8)

    # Country — text field (Greenhouse shows autocomplete suggestions)
    try:
        country_el = page.query_selector("input#country")
        if country_el and country_el.is_visible():
            country_el.click()
            country_el.fill(profile["country"])
            human_delay(0.5, 1.0)
            # Try clicking the first autocomplete suggestion
            try:
                suggestion = page.locator("[class*='suggestion'], [class*='autocomplete'] li").first
                if suggestion and suggestion.is_visible(timeout=2000):
                    suggestion.click()
            except Exception:
                page.keyboard.press("Tab")
    except Exception:
        pass

    human_delay(0.3, 0.7)

    # Location / city
    _safe_fill(page, "input#candidate-location", f"{profile['city']}, {profile['state']}")

    human_delay(0.3, 0.7)

    # Resume upload (#resume file input)
    try:
        resume_input = page.query_selector("input#resume, input[type='file']")
        if resume_input:
            resume_input.set_input_files(resume_pdf_path)
            human_delay(1.5, 2.5)
    except Exception:
        pass

    # LinkedIn custom question — label for="question_..." containing "LinkedIn"
    _fill_question_by_label(page, "LinkedIn", profile["linkedin"])

    # Visa sponsorship — answer "No"
    _fill_question_by_label(page, "Visa sponsorship", "No")
    _fill_question_by_label(page, "require Visa",     "No")
    _fill_question_by_label(page, "sponsorship",      "No")

    # "Why interested" open text — fill if blurb provided, else leave for user
    if interest_blurb:
        _fill_question_by_label(page, "why you are interested", interest_blurb)
        _fill_question_by_label(page, "interested in this role", interest_blurb)

    # EEO / demographic dropdowns (attempt; vary by employer)
    _fill_greenhouse_eeo(page, profile)

    human_delay(0.5, 1.0)


def _fill_greenhouse_eeo(page, profile: dict):
    """Attempt to fill standard Greenhouse EEO questions."""
    eeo_map = {
        "gender":    profile["gender"],
        "race":      profile["ethnicity"],
        "ethnicity": profile["ethnicity"],
        "veteran":   "I am not a protected veteran",
        "disability": "No, I don't have a disability",
    }
    for field_key, answer in eeo_map.items():
        for sel in [
            f"select[id*='{field_key}']",
            f"select[name*='{field_key}']",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    # Try to select by visible text (partial match)
                    options = el.locator("option").all()
                    for opt in options:
                        text = opt.inner_text()
                        if answer.lower() in text.lower() or text.lower() in answer.lower():
                            el.select_option(label=text)
                            break
            except Exception:
                pass


# ── LinkedIn Easy Apply ───────────────────────────────────────────────────────

def fill_linkedin(page, profile: dict, resume_pdf_path: str):
    """Handle LinkedIn Easy Apply multi-step modal."""
    human_delay(1, 2)

    try:
        # Click Easy Apply button
        btn = page.locator("button:has-text('Easy Apply')").first
        if btn and btn.is_visible():
            btn.click()
            page.wait_for_selector(".jobs-easy-apply-modal", timeout=10000)
            human_delay(1, 1.5)
    except Exception:
        return

    max_steps = 10
    for _ in range(max_steps):
        # Upload resume if step has file input
        try:
            fi = page.locator("input[type='file']").first
            if fi and fi.is_visible():
                fi.set_input_files(resume_pdf_path)
                human_delay(1, 2)
        except Exception:
            pass

        # Fill common fields
        _safe_fill(page, "input[id*='phoneNumber']", profile["phone_formatted"])

        # Advance: look for Next, Review, or Submit
        for btn_text in ["Next", "Review", "Continue"]:
            try:
                btn = page.locator(f"button:has-text('{btn_text}')").last
                if btn and btn.is_visible():
                    btn.click()
                    human_delay(1, 2)
                    break
            except Exception:
                pass
        else:
            break  # No navigation button found - done or on final review

        # Stop before Submit to let user review
        try:
            if page.locator("button:has-text('Submit')").is_visible():
                break
        except Exception:
            pass


# ── Generic handler ───────────────────────────────────────────────────────────

def fill_generic(page, profile: dict, resume_pdf_path: str):
    """Best-effort form fill for unknown ATS platforms."""
    human_delay(1, 2)

    field_map = {
        "first_name":  profile["first_name"],
        "fname":       profile["first_name"],
        "firstName":   profile["first_name"],
        "given_name":  profile["first_name"],
        "last_name":   profile["last_name"],
        "lname":       profile["last_name"],
        "lastName":    profile["last_name"],
        "family_name": profile["last_name"],
        "email":       profile["email"],
        "phone":       profile["phone_formatted"],
        "telephone":   profile["phone_formatted"],
        "linkedin":    profile["linkedin"],
    }

    for name, value in field_map.items():
        for attr in ["name", "id"]:
            try:
                el = page.query_selector(f"input[{attr}='{name}']")
                if el and el.is_visible():
                    el.fill(value)
                    human_delay(0.2, 0.5)
                    break
            except Exception:
                pass

    # File upload
    try:
        fi = page.locator("input[type='file']").first
        if fi:
            fi.set_input_files(resume_pdf_path)
            human_delay(1, 2)
    except Exception:
        pass


# ── Indeed handler (redirect to employer ATS) ─────────────────────────────────

def fill_indeed(page, profile: dict, resume_pdf_path: str):
    """
    Indeed typically redirects to the employer's ATS.
    We navigate to the apply URL and detect the real platform.
    """
    human_delay(1, 2)
    # After Indeed redirects, the page will be on the real ATS
    # The caller should re-detect the platform and call the right handler


# ── Main dispatch ─────────────────────────────────────────────────────────────

def fill_form(page, platform: str, profile: dict, resume_pdf_path: str,
              interest_blurb: str = ""):
    if platform == "greenhouse":
        fill_greenhouse(page, profile, resume_pdf_path, interest_blurb)
    elif platform == "linkedin":
        fill_linkedin(page, profile, resume_pdf_path)
    elif platform == "indeed":
        fill_indeed(page, profile, resume_pdf_path)
    else:
        fill_generic(page, profile, resume_pdf_path)
