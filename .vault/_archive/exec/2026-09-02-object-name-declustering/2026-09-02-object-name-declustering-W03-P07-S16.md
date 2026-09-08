---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:cdf220d26b11bbeef8f5926876937e15a0beca47e56368b326989a47bb1529ac'
step_id: 'S16'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test CLI argument contracts, structured output, default rehearsal, explicit apply, and exit semantics

## Scope

- `dev/quality/tests/test_object_name_declustering.py`

## Changes

- `M` `dev/quality/object_name_declustering.py`
- `A` `dev/quality/tests/test_object_name_declustering.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_declustering.py dev/quality/tests/test_object_name_declustering.py` -> `pass`
- `verify:` `independent current-byte S16 CLI safety review` -> `pass`

## Notes

Shared-tree commit `1c641ef7ad` materially landed the first 394 lines of the S16 test module. Commit `0dc6daea30` landed the remaining detector teeth and receipt-boundary correction. Mixed commit `fef064a4d8` landed the plan closure, review audit, and initial Step Record together with an unrelated TUI plan change. This record claims only the two implementation paths above.
