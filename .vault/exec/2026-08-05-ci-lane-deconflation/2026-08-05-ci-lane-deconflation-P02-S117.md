---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:cfe03c0d2e5025cc576529d25588f9f92056b4efd0c6b53a81d460e965fc4503'
step_id: 'S117'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Correct the historical novelty claim for the AEAT product/software identity blocker.

## Scope

- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md`
- `src/cadrumo/application/filing/_export.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S117.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s117-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: S117 corrected S116's novelty claim. The accepted ADR already decides the typed identity, selected-layout envelope keying, and refusal until authority exists. S116's 19-of-93 authored-layout exposure remains distinct evidence, not ADR novelty.
- This docs-only reconciliation changes no source, plan, baseline, threshold, or default index.
