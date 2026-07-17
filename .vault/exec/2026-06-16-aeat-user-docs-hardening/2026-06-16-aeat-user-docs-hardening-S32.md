---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden verification-reports.md

## Scope

- `docs/how-to/verification-reports.md`

## Description

- Verify-close: read `verification-reports.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M8 (report does not render the promised legal references / no `--json`): the page documents `--format json` as a GLOBAL flag placed BEFORE the command (`aeat --format json app modelo verification-report view <id>`), states each finding carries `legal_refs`/`source_refs`, and honestly notes that a few purely-structural checks legitimately have none.
- Confirm finding M10 (happy-path unreachable): the page's example is a first-period Modelo 303 with an activity-start-date that PASSES, so the documented `granted true` state is reachable top-to-bottom.
- Confirm finding m7 (`--casilla` silently rejects source-bound casillas): the page states `--casilla` works only on `manual` boxes and that a `bound` box is refused, naming the message.

## Outcome

- Page verified compliant at HEAD; findings M8, M10, m7 resolved (2026-06-19 documentation batch; the M8 fix was the global-flag-position meta-finding, not a per-command `--json`). Delta: none required.

## Notes

- Passphrase prerequisite and Spanish-runtime note present. CLI conformance gate green.
