---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8105ad0de84639acee01de0a2d4b2db46f3872f8fa0256726e7fbc13374ca8d8'
step_id: 'S222'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in models.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/transactions/models.py`

## Changes

- `M` `src/cadrumo/domain/transactions/models.py`
- `A` `src/cadrumo/domain/transactions/gross_validation.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S222.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s222-execution-self-review-audit.md`

## Notes

- Source commit `43b4b6880402ce65bb1592975f13052620dc1c4c` reduced `models.py` from 1,284 to 1,245 raw physical lines and added `gross_validation.py` at 51.
- The private gross-reconstitution diagnostic helper has one direct sibling home; `models.py` keeps its direct public API with no facade or re-export. AST review reported all 13 definitions conserved with no missing, extra, or duplicate definition, and reported the extracted helper AST-identical.
- The executor reported clean Ruff, format, compile, import, and diff checks; the literal transcripts are not retained, so these are qualified executor reports. The executor also reported 33 focused gross-invariant tests passed in 5.68 seconds; that retained result is qualified executor evidence.
