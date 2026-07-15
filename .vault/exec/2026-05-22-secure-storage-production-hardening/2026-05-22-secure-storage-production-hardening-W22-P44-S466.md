---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S466'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Verify real-entrypoint `config unlock` refusal and `config switch` activation

## Scope

- `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`

## Description

- Grounded the real entrypoint regression in the D1 command decision and the live custody registrar.
- Repointed this evidence row to the existing real-entrypoint lifecycle suite instead of adding a duplicate test.
- Ran `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py -m integration -n0 -q`.

## Outcome

All 35 real-entrypoint profile-lifecycle tests pass. They prove successful
`config switch` activation and the hard `config unlock` parse refusal without a
mocked or shadowed command tree.

## Notes

The repository's default pytest marker is `unit`; the initial unmarked command
selected no integration tests. The recorded command explicitly selects the
integration marker and disables xdist for the isolation-sensitive custody suite.
