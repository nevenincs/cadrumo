---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S25'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden read-live-aeat-data.md

## Scope

- `docs/how-to/read-live-aeat-data.md`

## Description

- Verify-close: read `read-live-aeat-data.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M21 (documented `pull` commands miss required args): the page now shows the required scope per verb - `justificante pull --modelo --year --period` (all three required), `filed pull --modelo --year` (`--year` required, `--period` or `--from-year`/`--to-year` to narrow), `notifications pull` (no scope).
- Confirm the systemic S-AUTH pattern: the page explains that the "Cl@ve identity" refusal actually means authentication is not configured (`auth_configured=False`), directing the reader to configure a provider rather than chase a Cl@ve mismatch.
- Confirm the never-write boundary and the `AEAT_LIVE_TESTS_ENABLED`-is-a-developer-setting clarification are stated.

## Outcome

- Page verified compliant at HEAD; finding M21 and the S-AUTH pattern resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- Read-only boundary is prominent ("never writes, files, or submits"); pull-vs-apply separation documented. CLI conformance gate green.
