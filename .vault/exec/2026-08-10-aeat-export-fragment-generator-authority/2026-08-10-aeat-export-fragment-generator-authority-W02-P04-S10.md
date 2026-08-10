---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:15993d00887591f0a7a95a89b42a173de9fafdb9a480b830b5062ba5831b3bcf'
step_id: 'S10'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Validate generated trees through the real registry loader before publication

## Scope

- `dev/registry/`

## Description

- Add a development-only isolated candidate context for one generated modelo revision.
- Reject extra modelos, direct revision files, links, missing or extra generated outputs, and unreviewed export-layout siblings.
- Load the candidate through `load_modelo_directory`, compare its sole layout to the fresh renderer result, and verify current provenance against joined design, semantic map, target, and field derivations.
- Load the same candidate through `ValidatedRegistryAuthority` and require the declared filing context to select the exact target revision.
- Add real loader and authority tests for positive validation, partial output, extra layouts, direct legacy input, malformed loader input, wrong period, wrong modelo, wrong revision, and provenance drift.

## Outcome

The generator now has a pre-publication validation boundary with no publication behavior and no legacy single-file, direct-revision, or old-tree fallback. The focused export-tree suite passed 17 tests; the full `dev/registry` suite passed 90 tests. Focused Ruff and BasedPyright were clean, and independent review found no critical, high, or medium issue.

## Notes

The whole `dev/registry` Ruff format and BasedPyright invocations still report unrelated pre-existing formatting and type debt outside S10. S10's focused static checks are clean.
