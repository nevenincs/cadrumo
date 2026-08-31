---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3c042d5a8a19913dbe30e1fc6a3a2c375fe97e762a0d1f01c29ce4b109c539f5'
step_id: 'S146'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in classification_assembly.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/ledger/classification_assembly.py`
- `src/cadrumo/application/ledger/_classification_assembly_rules.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S146.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s146-execution-self-review-audit.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/ledger/tests/test_classification_assembly.py` -> `38 passed in 14.24s` (root-run receipt)

## Notes

- Source commit `e2b99199a2` has the exact two-path manifest: `M` `src/cadrumo/application/ledger/classification_assembly.py` 1426 -> 1228 raw physical lines and `A` private `src/cadrumo/application/ledger/_classification_assembly_rules.py` at 213 lines. The sibling owns the table-probe/mapping family; public APIs and imports remain canonical in `classification_assembly.py`, with one private consumer.
- Root independently verified 33 aggregate AST definitions parity plus ruff, format, compile, and import-boundary checks. Legal rationale, comments, and docstrings moved intact rather than shortened.
- A broader direct-ledger batch supplied no terminal summary and is not claimed as passing. Peer-owned `src/cadrumo/tests/test_iva_category_singularity.py` was modified, deliberately untouched, and is outside this receipt.
- No source, plan, baseline, threshold, `--write-baseline`, `--accept-growth`, or default-index mutation occurred during this reconciliation.
