# Security policy

## Supported versions

Security fixes are applied to the latest commit on `main` only. There are no
long-term support branches.

---

## Reporting a vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

To report a vulnerability, open a
[GitHub private security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
on this repository. Private advisories are visible only to repository maintainers
until they are resolved and disclosed.

Your report should include:

- A clear description of the vulnerability and the potential impact.
- Steps to reproduce, with as much detail as possible.
- The version or commit hash you tested against.
- Any proof-of-concept code or screenshots (mark them as sensitive in the advisory).

We will acknowledge your report within **5 business days** and aim to release a fix
within **30 days** for high-severity issues. We will credit you in the advisory unless
you prefer to remain anonymous.

---

## Scope

### In scope

We consider the following classes of issues security vulnerabilities:

| Class | Example |
|-------|---------|
| Authentication bypass | Circumventing the session token that protects the local API |
| PII exposure | Any path that causes profile data, resume content, or API keys to be logged, written to an unprotected file, or returned in an API response to an unauthenticated caller |
| Cryptographic weakness | Flaw in how the Fernet key is derived, stored, or used in `api/security.py` |
| Path traversal | A file-upload or file-read endpoint that can be made to access files outside the project directory |
| Sensitive auto-fill bypass | Any code path that causes the bot to auto-fill a PAUSE-classified field (SSN, DOB, bank details, etc.) without human confirmation |
| Dependency with known CVE | A third-party package in `requirements.txt` with an exploitable vulnerability relevant to this project's threat model |
| Remote code execution | Any injection vector in job description parsing, form-field content, or API input that could lead to arbitrary code execution on the host |

### Out of scope

- Vulnerabilities that require physical access to the machine running the bot.
- Social engineering attacks against the user.
- Bugs in Playwright, Chromium, or other upstream dependencies that are not
  specific to how job-bot uses them. Please report those upstream.
- Issues in sites that the bot applies to (those are not our software).
- The bot applying to a job you did not intend — that is a usability bug, not a
  security vulnerability. File a regular issue for that.

---

## Security guarantees

The following properties are architectural commitments, not best-effort.
If any of them are violated, that is a security bug.

### API key encryption

The Anthropic API key is encrypted with a Fernet symmetric key before it is written
to `config/settings.json`. The Fernet key itself is derived from a randomly generated
session secret stored separately. The plaintext API key is held in memory only for the
duration of a single API call and is never written to disk, logged, or returned by any
API endpoint.

### No unexpected external network calls

The bot makes outbound network connections to exactly two categories of host:

1. Job board domains it is actively applying to (Indeed, LinkedIn, Greenhouse,
   Lever, Workday, and Google Jobs).
2. The Anthropic API (`api.anthropic.com`) when cover-letter generation is enabled
   and a valid API key is configured.

There are no telemetry calls, no analytics beacons, no update checks, and no calls
to any third-party service not listed above. You can verify this by auditing
`api/ai_writer.py` (the only file that imports `anthropic`) and running the bot
behind a network proxy with logging enabled.

### Local-only server

The FastAPI server (`api/main.py`) binds exclusively to `127.0.0.1`. It does not
listen on `0.0.0.0` or any network-accessible interface. The server is intended for
single-user local use only. Do not expose it to a LAN or the public internet without
adding your own authentication and TLS layer.

### Profile and output files are gitignored

`config/*_profile.json`, `resumes/`, `browser_profile/`, and `output/` are all
listed in `.gitignore`. These directories contain PII and must never be committed.
The example config (`config/profile.example.json`) contains only placeholder values
and is the only config file that belongs in version control.

### Sensitive fields always pause

Fields classified as PAUSE by `safety.py` (SSN, TIN, passport number, driver's
licence, date of birth, bank account number, routing number, and non-standard
criminal history questions) will never be auto-filled, regardless of how the form
label is phrased. This is a hard invariant enforced by the safety module and
verified by the test suite.

---

## Disclosure policy

Once a fix is merged, we will:

1. Publish the GitHub security advisory with full details.
2. Tag a new release noting the security fix in the changelog.
3. Credit the reporter (unless anonymity is requested).

We follow a **90-day coordinated disclosure** window. If a fix is not available
within 90 days, we will publish a mitigation advisory while work continues.
