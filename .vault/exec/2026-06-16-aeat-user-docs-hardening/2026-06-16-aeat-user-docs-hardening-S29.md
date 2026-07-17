---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden review-with-google-sheets.md

## Scope

- `docs/how-to/review-with-google-sheets.md`

## Description

- Verify-close: read `review-with-google-sheets.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M19 (`config google login` hangs silently in a non-interactive shell; verify/push mis-framed as offline): the login is now documented as an interactive browser gate, and the app refuses fast with an instructive typed message on non-interactive stdin (the blocking local-server wait is bounded to 300s); the Google-session requirement for verify / push --dry-run is stated rather than framed as offline.
- Confirm the OAuth login/namespace/push flow and its auth-gated behaviour are documented.

## Outcome

- Page verified compliant at HEAD; finding M19 resolved (google login hang fixed 2026-06-19, `_oauth_flow.py` + typed error + doc clarification). Delta: none required.

## Notes

- The retained OAuth client (so a later `config google login` reconnects) is documented on purpose. CLI conformance gate green.
