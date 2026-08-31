---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:80018349b0268745f638460f93b0168cb46bfcf3dbddce446a2b42e5f733799e'
step_id: 'S204'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in test_revision_span_matches_published_designs.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/_revision_span_design_support.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/_revision_span_boundary_support.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/_revision_span_coverage_support.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/_revision_span_declaration_support.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_span_design_parser.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_span_boundaries.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_span_coverage.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S204.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s204-execution-self-review-audit.md`
- `verify:` `git show --check d5f63d9e5aa80f3ad42e0ff98abab9fa0b94e05b` -> `pass`

## Notes

- Source provenance is `d5f63d9e5aa80f3ad42e0ff98abab9fa0b94e05b`, whose exact eight-path source manifest is the deleted test module plus the seven added siblings above. Raw physical counts are 886, 607, 572, 52, 54, 1059, and 234 lines respectively in manifest order after the deleted path; each is below the 1250-line ceiling. The source manifest contains no plan, baseline, threshold, or default-index mutation.
- Formal lossless review preserved 87 top-level definitions and 25 test definitions with no missing, extra, duplicate, or changed bodies; the raw replacement-character scan was zero and sibling test modules use direct private-support imports rather than facades or test-to-test re-exports.
- The executor reported focused pytest as 21 passed, 3 failed, and 18 warnings in 684.78 seconds. The three non-green outcomes are domain/corpus gates: Modelo 308's 2011 overlapping revisions, Modelo 184's unmeasured 2024 design, and the absent retired-to-reserved positive corpus case. This is reported evidence only, does not claim a baseline reproduction, and is not a green receipt. The executor also reported passing Ruff check/format and `compileall`.
- The executor reported a non-mutating global size scan with 56 unrelated non-green findings; no S204 sibling was over budget. No baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.
