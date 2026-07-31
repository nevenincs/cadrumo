---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:4b644754b66c621298efac30c676a2ed3cfc1dbf884fa94d60ff296d751cd386'
step_id: 'S12'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Emit per-profile coverage advisories on the calendar --all-profiles surface.

## Scope

- `src/aeat/entrypoints/cli/_overview.py`

## Description

- Accumulate per-profile coverage notices in the `calendar --all-profiles` path,
  tagging each notice's context with the profile label.
- Emit them on the multi-profile envelope and add a parallel text line, and exclude
  the coverage field from the per-profile dump so the advisory rides the Notice
  channel.

## Outcome

The multi-profile calendar surface no longer hides coverage advisories; each profile's
gap is distinguishable in the envelope. Single-profile calendar / agenda / backlog were
already wired. Remaining surfaces (status, explain, undeclared) are tracked as P03.S14.

## Notes
