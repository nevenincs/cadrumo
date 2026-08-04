---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5451b2a94bf325b9d166b91b32f2bfc6df92711fbcc9a6d56d6bb810d8815eb9'
step_id: 'S37'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add select_filesystem_retention_survivors as a pure function taking a timestamp projection, an optional cutoff, an optional count cap, and an optional total-byte ceiling, gated by tests covering each bound alone and composed

## Scope

- `src/cadrumo/core/paths.py`

## Description

- Add `select_filesystem_retention_survivors` in `core/paths.py` as a pure function over a timestamp projection, an optional cutoff, an optional count cap, and an optional total-byte ceiling.

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

This Step's checkbox was set in the prior reconciliation pass before the function existed; already-committed callers referenced it, leaving HEAD broken until `095bdc4ca2` landed the primitive. Recorded here for honesty; the Step is now genuinely satisfied.
