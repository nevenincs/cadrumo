---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1eb38562f2c7872b1337ce50a6b892262f7b51ffadfd66c1abae09dd823e3253'
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

This attestation commit is isolated to this execution record and its linked audit. It excludes the peer filing-relocation changes from its commit scope.

