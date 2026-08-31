---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c8829f7cc1bfb016dbf1d16f616fc493a833958ac3e7d2454735fa8c75856988'
step_id: 'S182'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in authority.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `A` `src/cadrumo/domain/calculations/registry/diagnostic_classification.py`

## Notes

The live subject is reduced from 1365 to 1142 lines and the added cohesive sibling is 253 lines. The size-budget baseline and thresholds were not changed.

The supplied focused evidence reports passing compile, import, direct-ownership, Ruff, and two boundary tests. The integration receipt is intentionally not represented as green: `1 passed, 2 failed, 4 deselected in 293.23s`; both failures are shared unrelated `corpus_catalogue` `applies_across` failures.

Source provenance is `4ced237398edb70bd54a0eef6550fda705dc0d70`. This attestation commit is isolated to this execution record and its linked audit. It excludes the peer filing-relocation changes from its commit scope.
