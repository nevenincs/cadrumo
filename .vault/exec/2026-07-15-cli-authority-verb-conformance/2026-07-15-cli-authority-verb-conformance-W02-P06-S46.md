---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:7c15f1b16472cf94ccaab960201ccc31df02adb11388633ce2dc82c757bd75aa'
step_id: 'S46'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove acquisition-lock cleanup is target scoped and repeatable with real lock files

## Scope

- `src/cadrumo/application/auth/tests/test_acquisition_lock.py`

## Description

- Add real-lock-file tests proving acquisition-lock cleanup is target-scoped and repeatable.
- Prove clearing one provider's lock leaves an unrelated provider's live lock file intact, and clearing one bucket's lock leaves the same provider's lock for another bucket intact.
- Prove clearing a target repeatedly removes the real lock once, then reports absence truthfully on the second and third calls without error.

## Outcome

Focused suite green: `uv run --no-sync pytest src/cadrumo/application/auth/tests/test_acquisition_lock.py -q` reports 7 passed (4 prior plus 3 new target-scoped and repeatable proofs). Ruff clean. The tests write and inspect real crash-recoverable lock files on disk with no mocks.

## Notes

Acquisition-lock paths are keyed by both bucket id and provider kind, so scoped cleanup is naturally target-specific; `clear_auth_acquisition_lock` returns the pre-clear status and treats an absent lock as a truthful no-op, which is what the repeatability proof asserts. No source-code change was required; only the missing proof was added.
