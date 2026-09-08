---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e87521c935efe5a9f6e6eaa9946e035a19045a8c9ee865d199b2b5b341729a98'
step_id: 'S192'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
