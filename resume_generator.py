"""
resume_generator.py
Calls Claude API to generate tailored resume JSON, then renders it as PDF using ReportLab.
Matches the Helvetica-based style used in existing Muhammad Umar Qasim resumes.
"""
import json
import os
import re

import anthropic
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

load_dotenv()

DARK   = colors.HexColor("#1A2B4A")
BLUE   = colors.HexColor("#2563EB")
GRAY   = colors.HexColor("#4B5563")
RULE_C = colors.HexColor("#CBD5E1")

RESUME_PROMPT = """\
You are a professional resume writer. Based on the job description below and the candidate's \
experience data, generate a tailored resume in JSON format.

CANDIDATE: Muhammad Umar Qasim
CONTACT: mq.umar55@gmail.com | (934) 235-5949 | Holbrook, NY | linkedin.com/in/muhammad-qasim02 | github.com/mq-umar

JOB DESCRIPTION:
{job_description}

CANDIDATE'S EXPERIENCE (select and rewrite the most relevant bullets - max 6 per role):
{experience_data}

Return ONLY valid JSON in this exact format (no markdown, no code blocks, just raw JSON):
{{
  "summary": "3-4 sentence professional summary targeting this specific role. No clichés. No 'results-driven' or 'passionate'. Human, direct, specific to the JD keywords.",
  "skills": [
    {{"label": "Category Name", "items": "item1, item2, item3, item4"}},
    {{"label": "Category Name", "items": "item1, item2, item3"}},
    {{"label": "Category Name", "items": "item1, item2, item3"}},
    {{"label": "Category Name", "items": "item1, item2"}},
    {{"label": "Languages", "items": "Python, PowerShell, JavaScript, SQL, Java, C++, PHP, HTML/CSS"}}
  ],
  "tony_bullets": [
    "bullet 1 (most relevant to this JD, with bold <b>keywords</b>)",
    "bullet 2",
    "bullet 3",
    "bullet 4",
    "bullet 5"
  ],
  "jovia_bullets": [
    "bullet 1 (most relevant to this JD)",
    "bullet 2",
    "bullet 3"
  ],
  "tony_title": "Job title that best matches this role (e.g. 'IT Supervisor - Microsoft 365 & Cloud Infrastructure')",
  "interest_blurb": "2-3 sentence answer to 'why are you interested in this role?' — specific to the company mission and the JD, not generic. First person. No buzzwords."
}}

Rules:
- Pull ATS keywords directly from the JD into the summary and bullets
- Bold the most important technical terms using <b>term</b> tags
- No em dashes anywhere (use hyphens or nothing instead)
- No buzzwords or AI-sounding phrases
- Each bullet must sound like something a real person would say in an interview
- Skills categories should be ordered by what this employer cares about most
- Max 5 bullets for Tony's Tacos, max 3 for Jovia
"""


def generate_resume_with_claude(jd_text: str, experience_data: str) -> dict:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = RESUME_PROMPT.format(
        job_description=jd_text[:8000],
        experience_data=experience_data,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    return json.loads(raw)


def _mk_styles():
    return {
        "name":    ParagraphStyle("N",  fontSize=22,   textColor=DARK, fontName="Helvetica-Bold",    alignment=TA_CENTER, spaceAfter=2),
        "contact": ParagraphStyle("C",  fontSize=9,    textColor=GRAY, fontName="Helvetica",         alignment=TA_CENTER, spaceAfter=6),
        "sec":     ParagraphStyle("SE", fontSize=10.5, textColor=BLUE, fontName="Helvetica-Bold",    spaceBefore=9,  spaceAfter=2, leading=14),
        "jtitle":  ParagraphStyle("JT", fontSize=10,   textColor=DARK, fontName="Helvetica-Bold",    spaceBefore=6,  spaceAfter=1),
        "co":      ParagraphStyle("CO", fontSize=9,    textColor=GRAY, fontName="Helvetica-Oblique", spaceAfter=3),
        "bul":     ParagraphStyle("BU", fontSize=9,    fontName="Helvetica", leftIndent=12, spaceAfter=2, leading=13),
        "norm":    ParagraphStyle("NM", fontSize=9,    fontName="Helvetica", spaceAfter=3, leading=13),
        "summ":    ParagraphStyle("SU", fontSize=9.5,  fontName="Helvetica", spaceAfter=4, leading=14),
        "skl":     ParagraphStyle("SL", fontSize=9,    textColor=DARK, fontName="Helvetica-Bold", spaceAfter=2),
        "skv":     ParagraphStyle("SV", fontSize=9,    fontName="Helvetica", spaceAfter=2, leading=13),
    }


def _hr():
    return HRFlowable(width="100%", thickness=0.6, color=RULE_C, spaceAfter=3, spaceBefore=1)


def _sec(title, s):
    return [Paragraph(title.upper(), s["sec"]), _hr()]


def _bullet(text, s):
    return Paragraph(f"• {text}", s["bul"])


def _skill_table(skill_rows, s):
    data = [
        [Paragraph(f"{label}:", s["skl"]), Paragraph(items, s["skv"])]
        for label, items in skill_rows
    ]
    t = Table(data, colWidths=[1.65 * inch, 5.5 * inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


CONTACT_LINE = (
    "Holbrook, NY 11741  |  (934) 235-5949  |  mq.umar55@gmail.com  |  "
    "linkedin.com/in/muhammad-qasim02  |  github.com/mq-umar"
)
EDU_LINE = (
    "Bachelor of Science - Computer Programming and Information Systems  |  "
    "Farmingdale State College, Farmingdale, NY  |  GPA: 3.66  |  August 2023 - May 2026"
)
CERTS_LINE = (
    "AWS Academy Cloud Foundations (July 2023)  |  "
    "TestOut Network Pro Certification (June 2022)"
)

PROJ_DASH_BULLETS = [
    "Built a production data platform integrating live POS exports, API sources, and Google Sheets inputs into a centralized dashboard used by leadership for daily performance tracking.",
    "Implemented multi-layer data validation and publish-gate logic ensuring accuracy and completeness of all metrics before surfacing to stakeholders.",
]
PROJ_Q_BULLET = (
    "Designed and built an AI productivity platform using Python, APIs, and local databases to "
    "streamline operational workflows, reporting, and task management."
)
PROJ_APP_BULLET = (
    "Built a secure CRUD web application with authentication, role-based access control, data "
    "validation, and SQL injection prevention via PDO prepared statements."
)


def generate_resume_pdf(resume_data: dict, output_path: str):
    """
    resume_data: dict returned by Claude API with keys:
        summary, skills (list of {label, items}), tony_bullets, jovia_bullets, tony_title
    """
    s = _mk_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    story = []

    # Header
    story.append(Paragraph("MUHAMMAD UMAR QASIM", s["name"]))
    story.append(Paragraph(CONTACT_LINE, s["contact"]))
    story.append(_hr())

    # Summary
    story += _sec("Professional Summary", s)
    story.append(Paragraph(resume_data["summary"], s["summ"]))

    # Skills
    story += _sec("Technical Skills", s)
    skill_rows = [(sk["label"], sk["items"]) for sk in resume_data["skills"]]
    story.append(_skill_table(skill_rows, s))

    # Experience
    story += _sec("Professional Experience", s)

    tony_title = resume_data.get("tony_title", "IT Supervisor")
    tony_bullets = [_bullet(b, s) for b in resume_data["tony_bullets"]]
    story.append(KeepTogether([
        Paragraph(tony_title, s["jtitle"]),
        Paragraph("Tony's Tacos  -  Garden City, NY  ·  <i>April 2026 - Present</i>", s["co"]),
        *tony_bullets,
    ]))

    story.append(Spacer(1, 4))

    jovia_bullets = [_bullet(b, s) for b in resume_data["jovia_bullets"]]
    story.append(KeepTogether([
        Paragraph("IT Service Desk Intern", s["jtitle"]),
        Paragraph(
            "Jovia Financial Credit Union  -  Westbury, NY  ·  "
            "<i>May 2024 - September 2024</i>",
            s["co"],
        ),
        *jovia_bullets,
    ]))

    # Projects
    story += _sec("Projects", s)

    story.append(KeepTogether([
        Paragraph("Multi-Location Operational KPI Dashboard System  |  2026", s["jtitle"]),
        Paragraph(
            "Python · REST APIs · Google Sheets API · Vercel  ·  "
            "<i>tonys-taco-kpi-dashboard.vercel.app</i>",
            s["co"],
        ),
        *[_bullet(p, s) for p in PROJ_DASH_BULLETS],
    ]))

    story.append(KeepTogether([
        Paragraph("AI Productivity Platform (Project Q)  |  2025-2026", s["jtitle"]),
        Paragraph("Python · APIs · SQLite · Workflow Automation · Claude", s["co"]),
        _bullet(PROJ_Q_BULLET, s),
    ]))

    story.append(KeepTogether([
        Paragraph(
            "Secure Full-Stack Web Application  |  Capstone - Farmingdale State College  |  Spring 2025",
            s["jtitle"],
        ),
        Paragraph("PHP · MySQL · JavaScript · HTML/CSS", s["co"]),
        _bullet(PROJ_APP_BULLET, s),
    ]))

    # Education
    story += _sec("Education", s)
    story.append(Paragraph(EDU_LINE, s["norm"]))

    # Certifications
    story += _sec("Certifications", s)
    story.append(Paragraph(CERTS_LINE, s["norm"]))

    doc.build(story)
    return output_path
