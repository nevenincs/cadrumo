---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a33b7b97d076cd91001f166fc54f23e07cba2bc6c3efa5a2a3476aecc160f04e'
step_id: 'S10'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test exact edits, unsupported constructs, changed-path bounds, and byte-level refusal behavior

## Scope

- `dev/quality/tests/test_object_name_transform.py`

## Changes

- `A` `dev/quality/tests/test_object_name_transform.py`
- `M` `dev/quality/object_name_transform.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_object_name_transform.py -q` -> `pass` (`30 passed`)
- `verify:` `uv run --no-sync ruff format --check dev/quality/tests/test_object_name_transform.py dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_transform.py dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_transform.py dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_transform.py dev/quality/tests/test_object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q dev/quality/object_name_transform.py dev/quality/tests/test_object_name_transform.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_transform.py dev/quality/tests/test_object_name_transform.py` -> `pass`
- `verify:` `independent S10 CRITICAL/HIGH re-review` -> `pass`

## Notes

Independent review exposed two high-severity detector gaps: same-package relative
consumer imports were normalized to absolute imports, and all repeated bindings
were refused before reference ambiguity was established. The minimal engine
correction preserves relative syntax and permits an isolated selected binding
while continuing to refuse references spanning ambiguous rebindings.

Shared-tree commits `33e9cba96d` and `8642691ae6` absorbed the substantive S10
engine and test changes before this Step close. Commit `33e9cba96d` also contains
an unrelated disposition-manifest change; this record claims only the engine
and test hunks listed above and does not rewrite shared history.
