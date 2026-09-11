---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:646f5defe9dd0fa1daa8e8a452626a6a0beeceeb2a3b1743e0f29f36ee0fbbd1'
step_id: 'S54'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [S | sonnet-high] Use the existing cross-revision drift assertion as the pilot's free retirement detector. It already asserts a specific casilla is absent from a later edition of modelo 100, backed four lines on by that edition's own retirement declaration. If the materialiser fails to honour retirement, that casilla is resurrected and the assertion fails without anything new being written. Note also that most callers classified indifferent are indifferent only because their fixtures declare a single edition, so they will not detect a materialiser defect either — indifference is not coverage, and the pilot's gates must not lean on them.

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `verify:` `pytest src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_1038_retirement_is_loaded` after the live 303 migration -> `pass`

## Notes

The assertion holds on the live tree, but it does not exercise this pilot. No 303 edition retires a lineage and modelo 100 is not migrated, so it will not bite until modelo 100 migrates. Retirement through the materialiser is covered instead by a planted 303 retirement in the migration tests.
