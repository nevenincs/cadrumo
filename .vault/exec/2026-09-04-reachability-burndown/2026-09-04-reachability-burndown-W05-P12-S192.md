---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3cc152b7e97be5298016dec2bae481adb99c3e53812592e9cdd265db6dec22c2'
step_id: 'S192'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only trash_rename_and_remove filesystem primitive, its private error-policy machinery, self-tests, and qualified-docstring assertion; correct the bucket directory-layout documentation to resolution-only ownership while retaining the accepted custody transaction as the sole physical profile-deletion owner.

## Scope

- `Bucket directory-layout module and self-tests`
- `qualified docstring conformance test`
- `profile-bucket lifecycle ownership`
- `exact reachability signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/bucket/directory_layout.py`
- `M` `src/cadrumo/adapters/persistence/storage/bucket/__init__.py`
- `D` `src/cadrumo/adapters/persistence/storage/bucket/tests/test_trash_rename_and_remove.py`
- `M` `src/cadrumo/tests/test_qualified_docstring_references_resolve.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/bucket/directory_layout.py src/cadrumo/adapters/persistence/storage/bucket/__init__.py src/cadrumo/tests/test_qualified_docstring_references_resolve.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/storage/bucket/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/storage/bucket/tests src/cadrumo/tests/test_qualified_docstring_references_resolve.py` -> `fail`

## Notes

- The exact detector reports 336 unused symbols and 18 orphan test modules, down from 337 and 18 before S192; no baseline, threshold, or disposition list changed.
- The combined qualified-docstring run passes all 132 retained bucket tests and fails four peer-owned resolver assertions: unrelated dangling references, a pre-existing population threshold, a Pydantic field resolution, and a lazy user-profile export. The removed trash helper has no remaining reference.
