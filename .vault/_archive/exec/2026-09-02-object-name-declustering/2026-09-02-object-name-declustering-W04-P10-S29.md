---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:51b1ef3575ff4f5250840ac6fc5ebb10164be455c24a50cffd4ecc266ec7c022'
step_id: 'S29'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Replace the vacuous churn test with one that can fail: perturb a real Python declaration so the current inventory digest actually moves, drive it through component derivation, rehearsal, receipt generation and replay preflight, and prove the case fails when receipt/current global-inventory equality is reintroduced, closing the end-to-end-churn-teeth gap S23 opened and S24 left standing (Luna max audit and mechanical)

## Scope

- `dev/quality/tests/`

## Changes

- `M` `dev/quality/tests/test_object_name_replay.py`
- `A` `.vault/audit/2026-09-07-object-name-declustering-s29-detector-review-audit.md`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_object_name_replay.py -q` -> `pass`
- `verify:` `temporary receipt/current equality mutation; focused replay detector` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/tests/test_object_name_replay.py` -> `pass`
