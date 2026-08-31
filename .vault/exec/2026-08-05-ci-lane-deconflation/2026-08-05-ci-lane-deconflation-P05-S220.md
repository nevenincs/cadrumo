---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:31581c90aa959e1a6583cf0c2c92a8cc29514d5b1f1fd08d21fe584d1a4b5b50'
step_id: 'S220'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_calculation_revision.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/modelos/tests/test_calculation_revision.py`

## Changes

- `R` `src/cadrumo/domain/modelos/tests/test_calculation_revision.py` -> `src/cadrumo/domain/modelos/tests/test_calculation_revision_evidence.py`
- `A` `src/cadrumo/domain/modelos/tests/_calculation_revision_test_support.py`
- `A` `src/cadrumo/domain/modelos/tests/test_calculation_revision_replay.py`
- `A` `src/cadrumo/domain/modelos/tests/test_calculation_revision_observations.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S220.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s220-execution-self-review-audit.md`
- `verify:` `git show --check 590fb81ff5c5fcd6b7f74491a932a6a7111ec16f` -> `pass`

## Notes

- Source provenance is `590fb81ff5c5fcd6b7f74491a932a6a7111ec16f`. Its exact five-path source manifest is the prior test module, renamed evidence sibling, added private support, added replay sibling, and added observations sibling above. Raw physical counts are 84 lines for support, 741 for evidence, 339 for replay, and 249 for observations; every new sibling is below the 1250-line ceiling. The source manifest contains no plan, baseline, threshold, or default-index mutation.
- Formal lossless review retained all 37 top-level definitions or classes and all 34 test definitions with no missing, extra, or changed bodies. The raw replacement-character scan was zero. Canonical tests were moved directly into the siblings; shared support owns only their common constants, class, and helpers, with direct imports and no facade or re-export.
- The executor reported a serial focused run of the three siblings as 47 passed and 1 failed in 80.13 seconds. The sole non-green result is an external production-rename census expectation: the test still expects `_amendment_actions.py` while the live source is `amendment_actions.py`. A rerun excluding precisely that external census test reported 47 passed and 1 deselected in 65.67 seconds. These are qualified executor-reported receipts, not a claim that the full focused family was newly green. Ruff check, Ruff format check, and `compileall` were reported passing.
- The executor reported a non-mutating global size scan with 57 unrelated non-green findings: 28 modules over budget, 9 stale module pins, 17 callables over budget, and 3 stale callable pins. No S220 sibling appeared. No baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.
