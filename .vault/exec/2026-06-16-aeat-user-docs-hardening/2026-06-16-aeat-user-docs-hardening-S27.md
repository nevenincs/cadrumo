---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S27'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden review-calculation-values.md

## Scope

- `docs/how-to/review-calculation-values.md`

## Description

- Verify-close: read `review-calculation-values.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M9 (ordering inversion + headline example fails): the page now sequences the work-unit create in "Before you start" first, states that the review commands refuse on a fresh unit and point to calculate first, and its `--casilla` example uses the manual box `06` (Retenciones), not the bound box `02` (Gastos), which `--casilla` refuses.
- Confirm finding m5 (`bindings list --missing` / readiness restatement): the page documents the `source` and `readiness` labels accurately and how to supply each source kind.
- Confirm S-PASS (passphrase) and S-PREREQ (active-profile + work-unit prerequisites) are addressed.

## Outcome

- Page verified compliant at HEAD; findings M9, m5, S-PASS, S-PREREQ resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- Documents the manual-vs-bound casilla distinction and the first-period prior-binding `=0` convention correctly. CLI conformance gate green.
