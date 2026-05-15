"""
resume_selector.py
Returns the right pre-built resume PDF path for a given profile and job title.
"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Muhammad ──────────────────────────────────────────────────────────────────

_M_DIR = Path(
    "/Users/admin/Library/Application Support/Claude/"
    "local-agent-mode-sessions/74cb488d-bd43-4e60-ae29-4b8d0cf4dd7d/"
    "287c1ab7-62ef-477f-a80b-7fc58dd0e864/"
    "local_b464a135-25f5-409a-89f5-8d6b7598869b/outputs"
)

_MUHAMMAD_MAP = [
    (["m365", "intune", "exchange", "sharepoint"],    "C1_M365_Azure_Intune_Admin.pdf"),
    (["iam", "identity"],                             "C8_IAM_Identity_Engineer.pdf"),
    (["devops", "cloud", "azure", "aws"],             "C4_Cloud_Infrastructure_Engineer.pdf"),
    (["security", "cyber", "soc"],                    "C5_Cybersecurity_Security_Analyst.pdf"),
    (["network"],                                     "C6_Network_Engineer_Admin.pdf"),
    (["msp", "managed service"],                      "C3_MSP_Managed_Services.pdf"),
    (["manager", "director"],                         "C9_IT_Manager_Director.pdf"),
    (["support", "helpdesk", "help desk", "specialist"], "C7_IT_Support_Specialist.pdf"),
]
_MUHAMMAD_DEFAULT = "C2_Systems_Administrator.pdf"

# ── Razia ─────────────────────────────────────────────────────────────────────

_R_DIR = BASE_DIR / "razia" / "razia_resumes"

_RAZIA_MAP = [
    (["vulnerability"],              "RC1_Vulnerability_Management.pdf"),
    (["endpoint", "intune"],         "RC2_Endpoint_Security_Intune.pdf"),
    (["macos", "apple"],             "RC3_macOS_Apple_MDM.pdf"),
    (["patch"],                      "RC4_Patch_Management_Compliance.pdf"),
    (["soc", "analyst"],             "RC5_SOC_Security_Analyst.pdf"),
    (["it security"],                "RC6_IT_Security_Engineer.pdf"),
    (["cloud", "azure"],             "RC7_Cloud_Azure_Security.pdf"),
    (["government", "dod"],          "RC8_Government_Defense.pdf"),
]
_RAZIA_DEFAULT = "RC6_IT_Security_Engineer.pdf"

# ── Dispatch ──────────────────────────────────────────────────────────────────

def pick_resume(title: str, notes: str = "", profile: str = "muhammad") -> str:
    """
    Returns the absolute path to the best-matching pre-built resume PDF.
    Falls back to the profile's default if no keyword matches.
    """
    haystack = (title + " " + notes).lower()

    if profile == "razia":
        keyword_map = _RAZIA_MAP
        resumes_dir = _R_DIR
        default     = _RAZIA_DEFAULT
    else:
        keyword_map = _MUHAMMAD_MAP
        resumes_dir = _M_DIR
        default     = _MUHAMMAD_DEFAULT

    for keywords, filename in keyword_map:
        if any(kw in haystack for kw in keywords):
            path = resumes_dir / filename
            if path.exists():
                return str(path)

    return str(resumes_dir / default)
