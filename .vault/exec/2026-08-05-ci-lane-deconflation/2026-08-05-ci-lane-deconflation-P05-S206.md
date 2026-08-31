---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:987894e287df51a2217077cbe176f4dbec784741016c0dc5a7d7ddfc863cdeee'
step_id: 'S206'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in withholding_bindings.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/withholding_bindings.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/_withholding_rows.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_withholding_observations.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S206.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s206-execution-self-review-audit.md`
- `verify:` `git show --check bfb6d1fc2d34b6f4c71c05455d99fa6470a7b62f` -> `pass`

## Notes

- Source provenance is `bfb6d1fc2d34b6f4c71c05455d99fa6470a7b62f`, whose exact three-path source manifest is the modified canonical module, the added private row-builder sibling, and the modified direct private-helper test consumer above. Raw physical counts are 929 lines for `withholding_bindings.py` and 1010 for `_withholding_rows.py`; both are below the 1250-line ceiling. The source manifest contains no plan, baseline, threshold, or default-index mutation.
- Formal review retained all 26 original top-level definitions or classes and all 34 test definitions with no missing or extra original definitions. The six intentional helper additions are `_finalise_190_identity_fields`, `_finalise_190_declaration_fields`, `_finalise_190_special_fields`, `_finalise_193_primary_fields`, `_finalise_193_instrument_fields`, and `_finalise_row_defaults`; only resolver-local-import and row-finaliser orchestration bodies changed. The raw replacement-character scan was zero. The canonical public module remains direct; the private test consumer imports the sibling directly rather than through a facade or re-export.
- The executor reported 34 focused `test_withholding_observations.py` tests passed in 5.25 seconds after the split. A broader seven-module family had passed 86 tests in 61.97 seconds before callable extraction; its final rerun was blocked before collection by the external missing `cadrumo.tests._env_loader` harness import. These are qualified executor-reported receipts, not a claim of a newly reproduced broad green run. Ruff check, Ruff format check, `compileall`, and direct imports were reported passing.
- The executor reported a non-mutating global size scan with 52 unrelated non-green findings: 30 modules over budget, 6 stale pins, and 16 callables over budget. No S206 module or callable appeared. No baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.
