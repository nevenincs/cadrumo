---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6410b6367cbb2eacd9a74a0e1bea04c41f8b69fb5cd5797ffe31bdd55ee337b7'
step_id: 'S196'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in `test_detail_record_observations.py` into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_withholding_observations.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S196.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s196-execution-self-review-audit.md`
- `verify:` `git show --check f497b88a157441c4756352445f76b241bcbf5a62` -> `pass`

## Notes

- Source provenance is `f497b88a157441c4756352445f76b241bcbf5a62`, whose manifest is exactly the two source paths above. Raw physical blob counts are 403 lines for `test_detail_record_observations.py` and 912 for `test_withholding_observations.py`; neither crosses the 1250-line ceiling. Its two-path manifest contains no threshold or baseline file.
- Independent AST comparison of the parent and both split blobs found 57 old top-level definitions, 20 retained plus 37 moved, with no missing, extra, or duplicate definitions; targeted import search found no imports from the old test module into the new sibling.
- The executor reported a focused pytest selection of 53 passed in 7.92s and passing compile/Ruff format/check results, but the literal command transcripts were not retained. Those reports are therefore not represented as fresh independently reproduced receipts here.
- A current non-mutating global size scan returned 58 findings and nonzero status, all elsewhere; neither S196 sibling appeared. This is not a global green result and no baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.
