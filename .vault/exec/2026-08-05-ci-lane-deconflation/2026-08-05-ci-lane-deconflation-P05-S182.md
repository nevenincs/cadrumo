---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5dc9c574e6db88b9ed31c82880481a0ea5ed9b21452609f2c3ea3537977ef908'
step_id: 'S182'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in authority.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `A` `src/cadrumo/domain/calculations/registry/diagnostic_classification.py`
- `M` `dev/registry/filing_export_proof.py`
- `M` `dev/registry/tests/test_filing_export_two_channel_proof.py`

## Notes

Source provenance is `4ced237398edb70bd54a0eef6550fda705dc0d70`. Its immutable physical/raw comparison is 1365 parent `authority.py` lines to 1142 committed `authority.py` lines, with a new 253-line `diagnostic_classification.py` sibling. The size-budget baseline and thresholds were not changed.

The supplied focused evidence reports passing compile, import, direct-ownership, Ruff, and two boundary tests. The integration receipt is intentionally not represented as green: `1 passed, 2 failed, 4 deselected in 293.23s`; both failures are shared unrelated `corpus_catalogue` `applies_across` failures.

The two `dev/registry` paths record the direct diagnostic-classification import repoints in `4ced237398edb70bd54a0eef6550fda705dc0d70`. Their shared working-tree hunk context also contains peer filing-relocation churn; that peer content is excluded from this attestation's source attribution and this artifact commit is isolated to the execution record and linked audit.
