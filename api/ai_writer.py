"""
Backend-only AI cover letter and ATS keyword writer.
Reads the encrypted Anthropic API key from config/settings.json,
decrypts it via api/security, and calls Claude to generate targeted content.
Never exposes the key to the frontend.
"""
import json
from pathlib import Path
from typing import Optional

BASE_DIR      = Path(__file__).parent.parent
SETTINGS_FILE = BASE_DIR / "config" / "settings.json"

# Haiku is fast and cheap — right model for per-application generation
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 350


def _get_api_key() -> Optional[str]:
    """Read and decrypt the Anthropic API key from settings.json."""
    try:
        if not SETTINGS_FILE.exists():
            return None
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
        enc = settings.get("anthropic_key_enc", "")
        if not enc:
            return None
        from api.security import decrypt
        return decrypt(enc)
    except Exception:
        return None


def generate_cover_letter(
    title: str,
    company: str,
    resume_name: str,
    profile: dict,
    jd_text: str = "",
    matched_keywords: Optional[list] = None,
) -> Optional[str]:
    """
    Generate an ATS-optimised cover letter using Claude.
    Returns the cover letter string, or None if the API key is missing or the call fails.
    Callers should fall back to the TF-IDF template on None.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    first  = profile.get("first_name", "")
    last   = profile.get("last_name", "")
    years  = profile.get("years_experience", "")
    city   = profile.get("city", "")
    state  = profile.get("state", "")
    kw_str = ", ".join((matched_keywords or [])[:8])

    jd_snippet = (jd_text or "")[:2000].strip()

    prompt = (
        f"Write a concise, ATS-optimised cover letter for {first} {last} "
        f"applying for the {title or 'this role'} position at {company or 'this company'}.\n\n"
        f"Candidate: {years} years of experience, based in {city}, {state}.\n"
        f"Resume file: {resume_name}\n"
    )
    if kw_str:
        prompt += f"Matched keywords from the job description: {kw_str}\n"
    if jd_snippet:
        prompt += f"\nJob description excerpt:\n{jd_snippet}\n"
    prompt += (
        "\nRequirements:"
        "\n- 3 short paragraphs, under 200 words total"
        "\n- Open with enthusiasm for THIS specific role and company"
        "\n- Middle paragraph: 2-3 concrete achievements relevant to the JD keywords"
        "\n- Close with a call to action"
        "\n- Never fabricate credentials, certifications, or dates"
        "\n- Do not include salutation or signature lines — body text only"
        "\n- Plain prose, no bullet points or markdown"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip() if message.content else ""
        return text if len(text) > 50 else None
    except Exception:
        return None


def suggest_ats_keywords(jd_text: str, resume_text: str = "") -> Optional[list]:
    """
    Return a list of ATS keywords from the JD that are worth emphasising.
    Returns None on failure; callers can skip this entirely.
    """
    api_key = _get_api_key()
    if not api_key or not jd_text:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    prompt = (
        "Extract the 10 most important ATS keywords from the following job description. "
        "Return ONLY a JSON array of strings, no commentary.\n\n"
        f"Job description:\n{jd_text[:3000]}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip() if message.content else "[]"
        # Extract JSON array even if Claude wraps it in markdown
        import re
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        return None
    except Exception:
        return None
