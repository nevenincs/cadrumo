---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:791898073e925e75b641a9387771ac44fa06bd062cc7a900b529501b91b39e7b'
step_id: 'S33'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Prove refusal for missing, duplicate, overlapping, conflicting, unknown-anchor, inapplicable, defaulted, legacy-derived, or source-hash-drifting profile authority, plus official Total: recovery, Num and signed-N behavior, and non-truncation of DP200000

## Scope

- `dev/registry/tests/`

## Description

- Reject non-TOML and non-regular render-profile directory entries before any profile authority is loaded.
- Add real-behavior mutations for conflicting width-17 authority and unknown parser anchors.
- Assert that a profile anchor cannot obtain a defaulted source cell.
- Read the hash-pinned official workbook independently and compare every `Total:` integer to the intermediate projection while preserving `DP200000` as a variable envelope.
- Assert the committed profile's explicit unsigned `Num` and signed `N` representations.

## Outcome

S33 passed. Profile authority now refuses legacy-derived sibling material instead of silently ignoring it. The focused profile and intermediate suite passed 33 tests; the broader `dev/registry` suite passed 138 tests. Ruff and BasedPyright passed on the scoped files. Independent Luna review found no critical, high, medium, or low issue.

## Notes

A repository formatting check reports pre-existing formatting differences outside this step's diff in the scoped files; no S33 change introduced a formatting diagnostic. No data loss, fallback, or compatibility surface was added.
