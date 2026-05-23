"""
resume_selector.py
ATS-grade resume selection using TF-IDF cosine similarity.

Priority order:
  1. Company/title exact override (instant — no PDF reading)
  2. TF-IDF cosine similarity scored against full JD text
  3. Keyword-count fallback if scikit-learn unavailable
  4. Ranked cluster defaults

PDF text is cached in-memory after first read so repeated calls are fast.
"""
import os
import re
from pathlib import Path

try:
    from pypdf import PdfReader
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _TFIDF_OK = True
except ImportError:
    _TFIDF_OK = False
    print("  [resume_selector] scikit-learn/pypdf not installed — using keyword fallback")

# ── Fit labels ─────────────────────────────────────────────────────────────────

def fit_label(score: float) -> str:
    if score >= 0.65: return "Strong Fit"
    if score >= 0.45: return "Good Fit"
    if score >= 0.30: return "Possible Fit"
    if score >= 0.15: return "Stretch"
    return "Low Fit"

BASE_DIR = Path(__file__).parent

# ── Resume folders ────────────────────────────────────────────────────────────

def _resume_folder(profile: str) -> Path:
    """Return the active resume folder for a profile. Falls back to a profile-named subfolder."""
    primary = BASE_DIR / "resumes" / profile
    if primary.exists() and any(primary.glob("*.pdf")):
        return primary
    # Check legacy <profile>/<profile>_resumes/ layout
    legacy = BASE_DIR / profile / f"{profile}_resumes"
    if legacy.exists() and any(legacy.glob("*.pdf")):
        return legacy
    return primary  # return even if empty — caller handles missing PDFs


def verify_resumes(profile: str = "") -> tuple[int, int, list[str]]:
    """Return (found, total, []) scanning the actual folder — no hardcoded list."""
    folder = _resume_folder(profile)
    found  = list(folder.glob("*.pdf")) if folder.exists() else []
    return len(found), len(found), []


# ── PDF text extraction + cache ───────────────────────────────────────────────

_pdf_cache: dict[str, str] = {}


def _pdf_text(path: str) -> str:
    if path not in _pdf_cache:
        if not _TFIDF_OK:
            _pdf_cache[path] = ""
            return ""
        try:
            reader = PdfReader(path)
            _pdf_cache[path] = " ".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            print(f"  WARNING: Could not read {Path(path).name}: {e}")
            _pdf_cache[path] = ""
    return _pdf_cache[path]


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── TF-IDF scoring ────────────────────────────────────────────────────────────

def score_resumes(jd_text: str, profile: str = "") -> list[tuple[str, float]]:
    """
    Score every resume in the folder against jd_text using TF-IDF cosine similarity.
    Returns [(filename, score), ...] sorted best to worst.
    """
    folder = _resume_folder(profile)
    pdfs   = sorted(folder.glob("*.pdf"))
    if not pdfs:
        return []

    if not _TFIDF_OK:
        return [(p.name, 0.0) for p in pdfs]

    clean_jd = _clean(jd_text)
    documents = [clean_jd]
    names     = []
    for pdf in pdfs:
        text = _pdf_text(str(pdf))
        documents.append(_clean(text))
        names.append(pdf.name)

    try:
        vec    = TfidfVectorizer(ngram_range=(1, 2), stop_words="english",
                                 max_features=5000, sublinear_tf=True)
        matrix = vec.fit_transform(documents)
        jd_vec = matrix[0]
        scores = [
            (name, float(cosine_similarity(jd_vec, matrix[i + 1])[0][0]))
            for i, name in enumerate(names)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores
    except Exception as e:
        print(f"  WARNING: TF-IDF scoring failed: {e}")
        return [(p.name, 0.0) for p in pdfs]


# ── Company overrides (checked before TF-IDF to skip PDF reads) ──────────────

_COMPANY_OVERRIDES: dict[str, str] = {
    "instride":   "Resume_InStride_Updated.pdf",
    "pasona":     "Job_PASONA_IT_Infrastructure_Engineer.pdf",
    "skopein":    "Job_Skopein_IT_Support_Engineer_L2.pdf",
    "brandrank":  "20_BrandRankAI_Frontend_Software_Engineer.pdf",
    "stepstone":  "10_StepStone_Junior_Analyst_RFP_AI.pdf",
    "imprint":    "11_Imprint_Software_Engineer.pdf",
    "flextrade":  "14_FlexTrade_Software_Developer_Cpp.pdf",
    "homeserve":  "15_HomeServe_DevOps_Engineer.pdf",
    "honeywell":  "19_Honeywell_Software_Engineer_Recent_Grad.pdf",
    "deloitte":   "18_Deloitte_Forward_Deployed_Engineer.pdf",
    "tinder":     "13_Tinder_Product_Analyst.pdf",
    "intuit":     "16_Intuit_Software_Engineer_1.pdf",
    "dev10":      "09_Dev10_Entry_Level_Data_Engineer.pdf",
}

_IBM_PICK: list[tuple[list[str], str]] = [
    (["strategy", "transformation", "consultant"], "01_IBM_AI_First_Strategy_Consultant.pdf"),
    (["data scientist", "data science"],           "02_IBM_Associate_Data_Scientist_2026.pdf"),
    (["cloud migration", "application developer"], "03_IBM_Application_Developer_Azure_Cloud.pdf"),
    (["ai software", "watsonx"],                   "06_IBM_AI_Software_Developer.pdf"),
    (["system support", "systems support"],        "07_IBM_System_Support_Tech_Apprentice.pdf"),
    (["backend", "back end", "back-end"],          "08_IBM_Backend_Developer_Intern_2026.pdf"),
    (["apprentice"],                               "04_IBM_Software_Engineer_Apprentice_A.pdf"),
]

_FALLBACK_ORDER = [
    "C1_M365_Azure_Intune_Admin.pdf",
    "C2_Systems_Administrator.pdf",
    "C4_Cloud_Infrastructure_Engineer.pdf",
    "C7_IT_Support_Specialist.pdf",
    "C5_Cybersecurity_Security_Analyst.pdf",
]

_KEYWORD_FALLBACK_MAP = [
    (["vulnerability", "vuln"],      "RC1_Vulnerability_Management.pdf"),
    (["endpoint", "intune", "mdm"],  "RC2_Endpoint_Security_Intune.pdf"),
    (["macos", "apple"],             "RC3_macOS_Apple_MDM.pdf"),
    (["patch", "compliance"],        "RC4_Patch_Management_Compliance.pdf"),
    (["soc", "analyst"],             "RC5_SOC_Security_Analyst.pdf"),
    (["it security", "security eng"],"RC6_IT_Security_Engineer.pdf"),
    (["cloud", "azure"],             "RC7_Cloud_Azure_Security.pdf"),
    (["government", "dod", "fed"],   "RC8_Government_Defense.pdf"),
]


# ── Public API ────────────────────────────────────────────────────────────────

def pick_resume(title: str, notes: str = "", profile: str = "",
                company: str = "", jd_text: str = "",
                exclude=None) -> str:
    """
    Return absolute path to the best-matching resume PDF.
    exclude: filenames to skip (for retry-on-missing-file logic).
    """
    exclude = exclude or set()
    return _pick_generic(title, notes, company, jd_text, profile, exclude)


# Keep old call signature for any code still using positional args
pick_best_resume = pick_resume


def get_matched_keywords(jd_text: str, resume_path: str, n: int = 6) -> list[str]:
    """
    Return the top-n TF-IDF feature tokens shared between JD and resume.
    Used for cover letter generation and logging.
    """
    if not _TFIDF_OK or not jd_text:
        return []
    try:
        resume_text = _pdf_text(resume_path)
        vec    = TfidfVectorizer(ngram_range=(1, 2), stop_words="english",
                                 max_features=5000, sublinear_tf=True)
        matrix = vec.fit_transform([_clean(jd_text), _clean(resume_text)])
        names  = vec.get_feature_names_out()
        # Element-wise product = terms that score high in BOTH documents
        overlap = np.asarray(matrix[0].todense()).flatten() * \
                  np.asarray(matrix[1].todense()).flatten()
        top_idx = overlap.argsort()[::-1][:n]
        return [names[i] for i in top_idx if overlap[i] > 0]
    except Exception:
        return []


def pick_resume_with_details(title: str, notes: str = "", profile: str = "",
                              company: str = "", jd_text: str = "",
                              exclude=None) -> tuple:
    """
    Returns (pdf_path, score, fit_label_str, matched_keywords, filename).
    All-in-one call for main.py — never crashes.
    """
    exclude = exclude or set()
    path    = pick_resume(title, notes, profile, company, jd_text, exclude)
    fname   = Path(path).name

    # Score only the chosen resume against the JD
    if jd_text and _TFIDF_OK:
        try:
            ranked  = score_resumes(f"{title} {company} {notes} {jd_text}", profile)
            score   = next((s for n, s in ranked if n == fname), 0.0)
        except Exception:
            score = 0.0
    else:
        score = 0.0

    keywords = get_matched_keywords(jd_text, path) if jd_text else []
    return path, score, fit_label(score), keywords, fname


def make_upload_copy(pdf_path: str, first_name: str, last_name: str, title: str) -> str:
    """
    Return path to a renamed copy of the resume with a professional filename.
    Format: FirstName_LastName_Job_Title.pdf
    Falls back to original path if copy fails.
    """
    import shutil as _shutil
    try:
        clean = re.sub(r"[^\w\s]", "", title or "").strip()
        clean = re.sub(r"\s+", "_", clean)[:45]
        fname = f"{first_name}_{last_name}_{clean}.pdf".strip("_")
        tmp_dir = BASE_DIR / "output" / "temp_resumes"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        dest = tmp_dir / fname
        _shutil.copy2(pdf_path, dest)
        return str(dest)
    except Exception:
        return pdf_path


def _find(folder: Path, filename: str, exclude: set):
    if filename in exclude:
        return None
    path = folder / filename
    return str(path) if path.exists() else None


def _pick_generic(title: str, notes: str, company: str,
                  jd_text: str, profile: str, exclude: set) -> str:
    """
    Universal resume picker that works for any profile:
      1. Company/title keyword overrides (fast — no PDF read)
      2. TF-IDF cosine similarity on full JD text
      3. Keyword fallback on title+notes alone
      4. Ranked fallback defaults
      5. Any PDF in folder
    """
    folder    = _resume_folder(profile)
    title_l   = title.lower()
    company_l = company.lower()
    full_jd   = f"{title} {company} {notes} {jd_text}"

    # 1. Company override (fast path)
    for keyword, filename in _COMPANY_OVERRIDES.items():
        if keyword in company_l or keyword in title_l:
            result = _find(folder, filename, exclude)
            if result:
                return result
            break

    # 2. Special sub-routing (e.g. IBM role variants)
    if "ibm" in company_l or "ibm" in title_l:
        for keywords, filename in _IBM_PICK:
            if any(kw in title_l for kw in keywords):
                result = _find(folder, filename, exclude)
                if result:
                    return result

    # 3. TF-IDF cosine similarity across all resumes in folder
    ranked = score_resumes(full_jd, profile)
    if ranked:
        top3 = ranked[:3]
        print(f"  Top matches: " + ", ".join(f"{n}({s:.3f})" for n, s in top3))
        for filename, score in ranked:
            if score > 0.0:
                result = _find(folder, filename, exclude)
                if result:
                    return result

    # 4. Ranked cluster fallback (works even if exact filenames not present)
    haystack = (title + " " + notes).lower()
    for keywords, filename in _KEYWORD_FALLBACK_MAP:
        if any(kw in haystack for kw in keywords):
            result = _find(folder, filename, exclude)
            if result:
                return result

    # 5. Static fallback defaults
    for filename in _FALLBACK_ORDER:
        result = _find(folder, filename, exclude)
        if result:
            return result

    # 6. Last resort — any PDF in folder
    for pdf in sorted(folder.glob("*.pdf")):
        if pdf.name not in exclude:
            return str(pdf)

    raise FileNotFoundError(f"No resume PDF found in {folder}")
