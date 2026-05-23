## What does this PR do?

<!-- Describe the change clearly. One paragraph is usually enough.
     If it closes an issue, add "Closes #NNN" on its own line below. -->

## Why is this change needed?

<!-- Explain the problem being solved or the improvement being made. -->

## How was it tested?

<!-- Describe what you did to verify the change works correctly.
     For safety-related changes, call out the specific test cases explicitly. -->

---

## Checklist

Before requesting review, confirm all of the following:

- [ ] `python tests/test_bot.py` passes — all 96 tests green.
- [ ] If I added or changed a safety rule, I also added a test that verifies the new behaviour.
- [ ] No real personal data is present anywhere in this PR — no real names, email addresses, phone numbers, resume content, API keys, or company names in source files, test fixtures, config files, screenshots, or commit history.
- [ ] No sensitive field (SSN, DOB, TIN, passport, bank details, routing number, criminal history beyond the standard felony pattern) can be auto-filled as a result of this change.
- [ ] No new outbound network connections are introduced beyond the documented ones (job board domains and `api.anthropic.com`).
- [ ] The local API server still binds to `127.0.0.1` only.
- [ ] No new dependencies are added that write plaintext credentials or PII to disk.
- [ ] Frontend changes run `npm run lint` cleanly inside `ui/`.
- [ ] I have read the [CONTRIBUTING.md](../CONTRIBUTING.md) safety-first policy and this change complies with it.

---

## Safety impact

<!-- Required field. If this change touches safety.py, form_filler.py,
     any PAUSE/FILL classification, scam detection, deduplication, or the
     review queue, describe the impact explicitly. If there is no safety
     impact, write "None." -->

## Screenshots (if UI change)

<!-- Attach before/after screenshots for any visual change.
     Blur or crop out personal information before attaching. -->
