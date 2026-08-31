---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e7024b3a4ad5ecda191cb49e93a20e73f9f7b27da0bbf4114ad2b86823f3aae5'
step_id: 'S218'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in calculation_revision.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/modelos/calculation_revision.py`

## Changes

- `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `A` `src/cadrumo/domain/modelos/calculation_revision_identity.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S218.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s218-execution-self-review-audit.md`

## Notes

- Source commit `3c458fb7d7f7af73766f8666a1e1ea18ba1e4269` reduced `calculation_revision.py` from 1,633 to 1,200 raw physical lines and added `calculation_revision_identity.py` at 468.
- Private canonicalization and hashing mechanics have one direct sibling home; the 15 public exports remain canonical in `calculation_revision.py`, with no facade or re-export. AST review reported all 44 definitions conserved with no missing, extra, or duplicate definition.
- The executor reported clean Ruff, format, compile, and import checks; literal transcripts are not retained, so these are qualified executor reports.
- Focused pytest produced no terminal receipt because concurrent workers stalled it; no test pass is claimed.
