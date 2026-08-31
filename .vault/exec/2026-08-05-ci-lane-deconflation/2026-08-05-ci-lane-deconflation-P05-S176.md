---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:cb85fa777e25d40585c8a62e0aa3bfb204e296b667345f98ca2dab6e93e1c49c'
step_id: 'S176'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _filing_projection_ref.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/core/_filing_projection_ref.py` (plan target; deleted)
- `src/cadrumo/core/filing_projection_ref.py` (authoritative public owner)
- `src/cadrumo/core/filing_projection_ref_support.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S176.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s176-execution-self-review-audit.md`

## Notes

- Source commit `f0bb7bcfdf` has the exact two-path source manifest: `M` `src/cadrumo/core/filing_projection_ref.py` 1258 -> 1236 raw physical lines and `A` `src/cadrumo/core/filing_projection_ref_support.py` at 23 lines. The plan's private target was deleted when `47c5185f2e` promoted the authoritative public owner; this record reconciles that displacement and claims no compatibility facade.
- Only `_STRING_WIRE_FIELDS` and `_validated_type_members` moved to the private support module. The public union, models, and API remain canonical in `filing_projection_ref.py`. Root rechecked 67 aggregate-definition AST parity and reported passing ruff, format, compile, and import-union smoke checks.
- Peer-owned `src/cadrumo/core/tests/test_filing_projection_ref.py` is modified and was deliberately untouched and not run. No test pass is claimed.
- No source, plan, baseline, threshold, `--write-baseline`, `--accept-growth`, or default-index mutation occurred during this reconciliation.
