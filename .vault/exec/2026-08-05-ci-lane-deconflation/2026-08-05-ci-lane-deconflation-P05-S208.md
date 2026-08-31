---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:55eb472dfea8e7e07831ecdaf0e49a116e03d2801ac3c0421489e6894d32839d'
step_id: 'S208'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in __init__.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/contribuyente/inventory/__init__.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py`
- `M` `src/cadrumo/application/aggregation/_inventory.py`
- `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `M` `src/cadrumo/application/inventory/_service.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/records.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/tests/test_acquisition_cost.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/tests/test_anexo_d_projection.py`
- `A` `src/cadrumo/domain/contribuyente/inventory/valuation.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S208.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s208-execution-self-review-audit.md`

## Notes

- The plan's named `inventory/__init__.py` is already the later inert namespace relocation (16 physical lines and `__all__ = ()`), so it was not a live size subject. The live displaced authority was `inventory/records.py`, measured at 1,650 physical lines before this work.
- Source commit `708f008d9f0bb884616a84bb19c76aa593863ff4` split that authority into canonical `records.py` (1,226 physical lines) and direct public `valuation.py` (461). The calculation/projection definitions have one canonical home in `valuation.py`; repository consumers were repointed directly, leaving no facade or re-export.
- AST comparison of the original record module against the two resulting modules found no missing definitions, extra definitions, or duplicate definitions. The retained record path remains canonical for record types.
- The executor reported focused pytest 147 passed in 54.06s and passing Ruff, formatting, compile, and diff checks. Literal command transcripts are not retained, so these are qualified executor reports, not fresh receipts.
- The global size audit was non-green with 56 unrelated findings (33 modules over budget, 6 stale pins, and 17 callables over budget). Neither resulting inventory module appeared; no global-green, baseline, threshold, or acceptance-growth claim is made.
- The initial execution record committed as `6ff141fec316a5331541be83587b53fd805d6685`; this correction supersedes its unqualified evidence wording.
