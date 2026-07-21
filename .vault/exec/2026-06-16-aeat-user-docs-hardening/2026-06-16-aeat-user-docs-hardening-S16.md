---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S16'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden justificante-receipts.md

## Scope

- `docs/how-to/justificante-receipts.md`

## Description

- Verify-close: read `justificante-receipts.md` against its 2026-06-18-audit findings and the systemic patterns and confirm resolution at HEAD.
- Confirm S-AUTH: `justificante pull` is documented as live-only, needing configured authentication; when auth is not set up the pull refuses before contacting AEAT (the Cl@ve-identity refusal), directing the reader to authenticate.
- Confirm S-QUIET: the on-page profile-create hint includes `--quiet` (the non-interactive form), so a reader following the suggestion does not hit the interactive-wizard wall.
- Confirm S-PASS (passphrase prerequisite) and the required scope args (`--modelo`, `--year`, `--period`).

## Outcome

- Page verified compliant at HEAD; the S-AUTH, S-QUIET, S-PASS patterns are addressed. Delta: none required.

## Notes

- The receipt is pulled and stored as encrypted evidence in the profile (bytes-not-links). CLI conformance gate green.
