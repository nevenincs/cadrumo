---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Run the focused registry test suites for all five touched modelos (test_modelo_202_registry.py, test_modelo_123_registry.py, test_modelo_151_registry.py, test_modelo_714_registry.py, test_modelo_210_registry.py) plus every new gate-behaviour test file and confirm a clean pass

## Scope

- `src/aeat/domain/calculations/registry/tests/`

## Description

- Ran the focused registry test suites for all five touched modelos (`test_modelo_202_registry.py`, `test_modelo_123_registry.py`, `test_modelo_151_registry.py`, `test_modelo_714_registry.py`, `test_modelo_210_registry.py`) plus every new gate-behaviour test file (`test_verification_m202_advisory.py`, `test_verification_m123_advisory.py`, `test_verification_m151_advisory.py`, `test_verification_m714_advisory.py`, `test_verification_m210_advisory.py`) plus the two operator-generic suites the new `casilla_equals_implies_nonzero` operator extended (`test_verification_substance.py`, `test_verification_substance_workflow.py`) in a single invocation, capturing the full output to a log file per the pytest-background-capture discipline rather than truncating through a tail/head pipe.
- Confirmed 133 tests passed with zero failures across all twelve files.
- Ran the broader registry build/validate selection (`pytest -k "validate or build_snapshot or registry" src/aeat/domain/calculations/registry/tests`) to confirm the new `casilla_equals_implies_nonzero` operator and its registry-build validator do not regress registry-load correctness anywhere else in the tree.
- Found one in-scope regression: `test_registry_validator_modules_stay_below_complexity_baselines` failed because `_validate_surfaces.py` grew to 356 lines (the new `_casilla_equals_implies_nonzero_predicate_failures` validator pushed it past the 300-line default ceiling for un-baselined validator modules). Fixed by adding a reviewed-baseline entry `"_validate_surfaces.py": 356` to `_VALIDATOR_MODULE_LINE_BASELINES` in `test_registry_reviewability.py`, following the exact precedent of the ten other organically-grown validator modules already carrying explicit baseline entries (verified via `git log -p` that each prior baseline bump set the ceiling to the exact post-growth line count, not a rounded headroom).
- Re-ran the broader registry build/validate selection after the fix; confirmed only two failures remain, neither touching any file this feature modified (`git status --short` against the affected paths returns empty): `test_cross_dependency_roles_match_supported_modelo_hierarchy` (Modelo 390 `source_periods` arity) and `test_modelo_100_renta_section_constructs_classify_registered_relation_sources` (Modelo 100 `renta-real-estate-capital` construct), both owned by concurrently active peer campaigns per `full-tree-gate-must-distinguish-owner`.

## Outcome

All 133 feature-specific tests pass cleanly. The broader registry build/validate selection (3,646 tests) passes except for two pre-existing, owner-unrelated failures (Modelo 390 and Modelo 100, neither in a file this feature touched). The one in-scope regression discovered during this Step (`_validate_surfaces.py` exceeding the reviewability line-count ceiling) was fixed in the same Step.

## Notes

No data loss. One in-scope regression found and fixed (the `_validate_surfaces.py` reviewability baseline, see Description). Two unrelated pre-existing failures (M390, M100) triaged as peer-owned and left untouched, per `full-tree-gate-must-distinguish-owner`; not actioned by this Step.
