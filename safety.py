"""
safety.py — Sensitive field detection, scam detection, compliance rules.

This module is the single source of truth for what the bot is and is NOT
allowed to auto-fill. Every decision here prioritizes candidate safety,
legal accuracy, and prevention of false or harmful submissions.

Design principles:
  - Never fill SSN, passport, driver's license number, full DOB, or bank info
  - Use confirmed candidate facts for standard work-auth / citizenship / felony questions
  - Default EEO voluntary fields (race, gender, disability, veteran) to
    "Prefer not to answer" UNLESS the user explicitly set a value
  - Pause for any criminal history question that is not the exact standard
    "convicted of a felony" pattern
  - Detect scam jobs before wasting time or submitting real data
  - Enforce per-company cooldown and salary minimums
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent


# ── Confirmed candidate facts ─────────────────────────────────────────────────
# These are hard facts set by the candidate. The bot may auto-answer questions
# that match these patterns exactly. Any deviation → human review.

CONFIRMED_FACTS = {
    "authorized_to_work_us":      True,
    "require_sponsorship":        False,
    "require_future_sponsorship": False,
    "us_citizen":                 True,
    "felony_conviction":          False,
    "criminal_record_standard":   False,  # "convicted of a crime" standard wording only
}


# ── Patterns that REQUIRE pausing — never auto-fill these ────────────────────

_PAUSE_PATTERNS: list[tuple[str, str]] = [
    # Government identity numbers
    (r"\bssn\b|social security ?(number|no\.?|#|num)|tax id(entification)?\b|tin\b|fein\b",
     "SSN / Tax ID"),
    (r"passport ?(number|no\.?|#|id\b|num)",
     "Passport Number"),
    (r"driver'?s? licen[sc]e ?(number|no\.?|#|id\b|num)|dl ?(number|no\.?|#)\b",
     "Driver's License Number"),
    (r"(full |complete )?date of birth|birth ?(day|date)|dob\b|\bbirth year\b",
     "Date of Birth"),
    # Financial
    (r"bank account|routing ?(number|#)|account ?(number|#)|direct deposit|ach\b|swift code",
     "Bank / Financial Information"),
    # Criminal — unusual wording requiring review
    (r"\bmisdemeanor\b",
     "Criminal History — Misdemeanor Wording"),
    (r"pending (charge|arrest|case)|arrest(ed)?\b|charge[sd]? with",
     "Criminal History — Pending / Arrest"),
    (r"expunge[d]?|seal(ed)? (record|conviction)|juvenile (record|offense)",
     "Criminal History — Expungement / Sealed"),
    (r"(offense|conviction).*(in the (last|past)|within \d+\s*year)",
     "Criminal History — Time-Bounded Wording"),
    (r"(any|other|all) ?(crime|criminal|offense|conviction|felony|misdemeanor)",
     "Criminal History — Broad / Expanded Scope"),
    # Medical / protected class beyond standard EEO
    (r"(specific |nature of |describe|detail).*(disability|medical|condition)",
     "Medical Condition Details"),
    (r"pregnancy|pregnant|family (planning|status)|maternity",
     "Pregnancy / Family Status"),
    (r"religion\b|religious (belief|practice|affiliation)",
     "Religion"),
    (r"sexual orientation|lgbtq|gender identity",
     "Sexual Orientation / Gender Identity"),
    (r"political (affiliation|party|belief)|union (member|card)",
     "Political / Union Affiliation"),
    # SSN fragments that are still too sensitive
    (r"last (4|four) (digits? of )?(ssn|social security)|ssn (last|ending)",
     "SSN Partial"),
]

# Pre-compile for performance
_PAUSE_COMPILED = [
    (re.compile(pattern, re.I), label)
    for pattern, label in _PAUSE_PATTERNS
]


# ── Criminal history — standard wording auto-fill ─────────────────────────────
# Only these exact patterns are considered "standard felony questions"
# that the bot may answer with the confirmed fact (No).

_FELONY_STANDARD_PATTERNS: list[str] = [
    r"(ever |have you )?(been )?convicted of a felony",
    r"any felony conviction",
    r"felony (conviction|record)\b",
]
_FELONY_COMPILED = [re.compile(p, re.I) for p in _FELONY_STANDARD_PATTERNS]

_CRIME_STANDARD_PATTERNS: list[str] = [
    r"(ever |have you )?(been )?convicted of (a )?crime",
    r"any criminal conviction",
    r"criminal (conviction|record|background)\b(?!.*misdemeanor)(?!.*other)(?!.*any)",
]
_CRIME_COMPILED = [re.compile(p, re.I) for p in _CRIME_STANDARD_PATTERNS]


# ── Work authorization — safe auto-fill ───────────────────────────────────────

_WORK_AUTH_PATTERNS: list[str] = [
    r"(legally |lawfully )?(authorized|eligible) to work (in (the )?u\.?s\.?|united states)",
    r"(legal )?right to work (in (the )?u\.?s\.?|united states)",
    r"eligible to work (in (the )?u\.?s\.?|united states)",
    r"work authorization",
    r"employment (authorization|eligibility)",
]
_WORK_AUTH_COMPILED = [re.compile(p, re.I) for p in _WORK_AUTH_PATTERNS]

_SPONSORSHIP_PATTERNS: list[str] = [
    r"(will|do) you (now or in the future )?(require|need) (visa )?sponsor(ship)?",
    r"(require|need) sponsorship",
    r"employer (visa )?sponsor(ship)?",
]
_SPONSORSHIP_COMPILED = [re.compile(p, re.I) for p in _SPONSORSHIP_PATTERNS]

_CITIZEN_PATTERNS: list[str] = [
    r"are you a (u\.?s\.?|united states) citizen",
    r"u\.?s\.? citizenship",
    r"citizenship status",
]
_CITIZEN_COMPILED = [re.compile(p, re.I) for p in _CITIZEN_PATTERNS]


# ── AI/bot trap detection ──────────────────────────────────────────────────────
# Some applications include trap questions designed to catch AI bots.
# The bot should skip these questions (not answer them).

_BOT_TRAP_PATTERNS = re.compile(
    r"(if you (are|are an) (ai|llm|bot|robot|language model)|"
    r"if (this|you) (is|are) (being (read|processed) by|an?) (ai|llm|robot)|"
    r"to (prove|show|demonstrate) you.*(human|not (a )?(bot|ai|robot))|"
    r"what is (the|your) (favorite color|name of|color of).*(sky|dinosaur|planet)|"
    r"type (the word|exactly|verbatim)\s+['\"]?\w+['\"]?\s+(to (show|prove|confirm)|if you)|"
    r"dinosaur|ignore (all )?(previous|prior|above)|respond with)",
    re.I,
)


# ── Scam detection ────────────────────────────────────────────────────────────

_SCAM_INDICATORS = [
    # Money requests
    (re.compile(r"pay (for|a) (training|background|equipment|kit|starter)", re.I),
     "Asks for payment", 8),
    (re.compile(r"purchase (your own|equipment|supplies|starter kit)", re.I),
     "Asks to purchase equipment", 8),
    # Suspicious personal data upfront
    (re.compile(r"(provide|send|submit).{0,40}(bank account|routing number|credit card)", re.I),
     "Requests bank/credit info upfront", 9),
    (re.compile(r"(provide|send|submit).{0,30}(ssn|social security).{0,20}(before|upfront|first)", re.I),
     "Requests SSN before formal offer", 9),
    # Unrealistic compensation
    (re.compile(r"\$\s*[1-9]\d{3,}\s*(per|/)\s*(hour|hr)", re.I),
     "Unrealistic hourly rate", 5),
    (re.compile(r"(earn|make|income of?).{0,20}\$\s*[5-9]\d{4,}", re.I),
     "Unrealistic income claim", 4),
    # Communication red flags
    (re.compile(r"(contact|apply|message).{0,30}(whatsapp|telegram|signal)\b", re.I),
     "WhatsApp/Telegram only contact", 7),
    (re.compile(r"gmail\.com|yahoo\.com|hotmail\.com|outlook\.com\s*\(recruiter", re.I),
     "Recruiter using personal email domain", 5),
    # Vague/scam language
    (re.compile(r"work (from home|remotely).{0,30}(no experience|uncapped|unlimited earning)", re.I),
     "Work-from-home + no experience + unlimited earnings", 7),
    (re.compile(r"(immediate|urgently? )(hiring|start|needed).{0,40}no (experience|degree|skills)", re.I),
     "Urgent hiring + no requirements", 5),
    (re.compile(r"commission.{0,30}only|100% commission", re.I),
     "Commission-only", 4),
    # Completely fake job
    (re.compile(r"(ssn|social security|bank).{0,30}(required|needed|mandatory).{0,30}apply", re.I),
     "Requires SSN/bank info to apply", 10),
]

_SCAM_THRESHOLD = 7  # Sum of risk scores above this → flag as scam


# ── Public API ────────────────────────────────────────────────────────────────

def classify_field(label: str) -> dict:
    """
    Classify a form field label and return an action dict.

    Returns:
      {
        "action":  "fill"        → safe to auto-fill from profile
                   "prefer_not" → use "Prefer not to answer" (EEO voluntary)
                   "pause"      → stop, flag for human review
                   "skip"       → bot trap or irrelevant
                   "confirmed"  → use a confirmed candidate fact
        "reason":  str           → human-readable explanation
        "value":   str | None    → pre-filled value for "confirmed" actions
      }
    """
    label_lower = label.lower().strip()

    # ── Bot trap detection ────────────────────────────────────────────────────
    if _BOT_TRAP_PATTERNS.search(label_lower):
        return {"action": "skip", "reason": "Bot trap / AI detection question detected — skipping",
                "value": None}

    # ── Hard pause fields — never auto-fill ──────────────────────────────────
    for pattern, description in _PAUSE_COMPILED:
        if pattern.search(label_lower):
            return {"action": "pause",
                    "reason": f"Sensitive field detected: {description}",
                    "value": None}

    # ── Confirmed auto-fill — work authorization ──────────────────────────────
    for pattern in _WORK_AUTH_COMPILED:
        if pattern.search(label_lower):
            return {"action": "confirmed",
                    "reason": "Work authorization — confirmed: Yes",
                    "value": "Yes"}

    # ── Confirmed auto-fill — sponsorship ────────────────────────────────────
    for pattern in _SPONSORSHIP_COMPILED:
        if pattern.search(label_lower):
            return {"action": "confirmed",
                    "reason": "Visa sponsorship — confirmed: No",
                    "value": "No"}

    # ── Confirmed auto-fill — US citizenship ──────────────────────────────────
    for pattern in _CITIZEN_COMPILED:
        if pattern.search(label_lower):
            return {"action": "confirmed",
                    "reason": "US citizenship — confirmed: Yes",
                    "value": "Yes"}

    # ── Confirmed auto-fill — standard felony question ────────────────────────
    for pattern in _FELONY_COMPILED:
        if pattern.search(label_lower):
            return {"action": "confirmed",
                    "reason": "Standard felony question — confirmed: No conviction",
                    "value": "No"}

    # ── Confirmed auto-fill — standard crime conviction ───────────────────────
    for pattern in _CRIME_COMPILED:
        if pattern.search(label_lower):
            # Double-check this doesn't match any expanded/unusual wording
            # (the regex already excludes misdemeanor/any/other via negative lookahead)
            return {"action": "confirmed",
                    "reason": "Standard criminal conviction question — confirmed: No",
                    "value": "No"}

    return {"action": "fill", "reason": "Standard field", "value": None}


def has_sensitive_flags(field_log: list) -> list[str]:
    """
    Check a filled field_log for any _meta_sensitive_pause sentinels.
    Returns a list of reason strings for each flagged field.
    """
    reasons = []
    for entry in field_log:
        if entry.get("field") == "_meta_sensitive_pause":
            reasons.append(entry.get("value", "Unknown sensitive field"))
    return reasons


def is_scam_job(company: str, title: str, jd_text: str, url: str = "") -> tuple[bool, list[str]]:
    """
    Scan job metadata for scam indicators.
    Returns (is_scam, list_of_reasons).
    """
    text = f"{company} {title} {jd_text} {url}".lower()
    reasons = []
    total_score = 0
    for pattern, reason, score in _SCAM_INDICATORS:
        if pattern.search(text):
            reasons.append(reason)
            total_score += score
    return total_score >= _SCAM_THRESHOLD, reasons


def check_company_cooldown(company: str, profile_name: str,
                            cooldown_days: int = 30) -> tuple[bool, Optional[str]]:
    """
    Check if we applied to this company within the cooldown window.
    Returns (on_cooldown: bool, last_applied_date: str | None).
    """
    if cooldown_days <= 0 or not company:
        return False, None

    company_lower = re.sub(r"[^a-z0-9]", "", company.lower())
    if len(company_lower) < 3:
        return False, None

    cutoff = datetime.now() - timedelta(days=cooldown_days)
    jsonl_path = BASE_DIR / "output" / f"results_{profile_name}.jsonl"
    if not jsonl_path.exists():
        return False, None

    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    status = entry.get("status", "")
                    if status not in ("submitted", "submitted_manually"):
                        continue
                    co = re.sub(r"[^a-z0-9]", "", (entry.get("company", "") or "").lower())
                    if not co or co not in company_lower and company_lower not in co:
                        continue
                    # Check if within cooldown window
                    ts_str = entry.get("timestamp", "")
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                    except Exception:
                        continue
                    if ts >= cutoff:
                        return True, ts_str
                except Exception:
                    pass
    except Exception:
        pass
    return False, None


def is_salary_below_minimum(jd_text: str, notes: str, profile: dict) -> tuple[bool, str]:
    """
    Check if a job's salary is explicitly below the profile's minimum.
    Returns (is_below: bool, reason: str).
    Only rejects if salary is EXPLICITLY stated AND below minimum.
    If salary is not listed → never rejects.
    """
    minimum = profile.get("salary_minimum", 0)
    if not minimum or minimum <= 0:
        return False, ""

    text = f"{notes} {jd_text}".replace(",", "")

    # Hourly detection (convert to annual)
    hourly_m = re.search(r"\$(\d+\.?\d*)\s*[-–/]?\s*\$?(\d+\.?\d*)?\s*/?\s*hr", text, re.I)
    if hourly_m:
        hi = float(hourly_m.group(2) or hourly_m.group(1))
        annual = int(hi * 2080)
        if annual < minimum:
            return True, f"Salary ${annual:,}/yr (hourly-converted) below minimum ${minimum:,}"
        return False, ""

    # Annual range
    range_m = re.search(r"\$?(\d+)\s*[kK]?\s*[-–]\s*\$?(\d+)\s*[kK]", text)
    if range_m:
        lo, hi = int(range_m.group(1)), int(range_m.group(2))
        if hi < 2000:
            hi *= 1000
        if lo < 2000:
            lo *= 1000
        # If the HIGH end is below minimum → definitely below
        if hi < minimum:
            return True, f"Salary range up to ${hi:,} below minimum ${minimum:,}"
        return False, ""

    # Single value
    single_m = re.search(r"\$(\d+)\s*[kK]", text, re.I)
    if single_m:
        v = int(single_m.group(1))
        annual = v * 1000 if v < 2000 else v
        if annual < minimum:
            return True, f"Salary ${annual:,} below minimum ${minimum:,}"
        return False, ""

    return False, ""  # No salary listed → do not reject


def save_needs_review(profile_name: str, entry: dict, reasons: list[str]) -> None:
    """
    Persist an application that needs human review to output/needs_review.jsonl.
    Deduplicates by (profile, job_url) — won't add the same URL twice.
    """
    output_dir = BASE_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "needs_review.jsonl"

    job_url = entry.get("job_url", entry.get("url", ""))
    # Dedup: skip if same profile+URL already in queue
    if job_url and path.exists():
        try:
            with open(path) as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                        if r.get("profile") == profile_name and r.get("job_url") == job_url:
                            return  # already queued
                    except Exception:
                        pass
        except Exception:
            pass

    record = {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "profile":        profile_name,
        "company":        entry.get("company", ""),
        "title":          entry.get("title", ""),
        "job_url":        job_url,
        "platform":       entry.get("platform", ""),
        "resume":         entry.get("selected_resume", ""),
        "score":          entry.get("resume_score", ""),
        "fit_label":      entry.get("fit_label", ""),
        "review_reasons": reasons,
        "status":         "needs_review",
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_needs_review(profile_name: Optional[str] = None) -> list[dict]:
    """Load all needs_review records, optionally filtered by profile."""
    path = BASE_DIR / "output" / "needs_review.jsonl"
    if not path.exists():
        return []
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if profile_name and r.get("profile") != profile_name:
                        continue
                    records.append(r)
                except Exception:
                    pass
    except Exception:
        pass
    return records
