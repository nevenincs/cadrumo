---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:58d4b6fabeebc93e946010495cd012c7e36e86a01a90bdca7b33a70fc9af7c99'
step_id: 'S373'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Collapse manual handling to live bundled-manifest verification, deleting the unwired HTTP fetch subsystem, exact URL-roster tests, and newly test-only atomic stream writer.

## Scope

- `manual fetch module and tests`
- `core atomic-write helper and tests`
- `application manual reader`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/manuals/fetch.py`
- `M` `src/cadrumo/domain/manuals/tests/test_fetch.py`
- `M` `src/cadrumo/core/atomic_write.py`
- `M` `src/cadrumo/core/tests/test_atomic_write.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/manuals/fetch.py src/cadrumo/domain/manuals/tests/test_fetch.py src/cadrumo/core/atomic_write.py src/cadrumo/core/tests/test_atomic_write.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/manuals/tests/test_fetch.py src/cadrumo/core/tests/test_atomic_write.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The broader `src/cadrumo/application/registry/tests/test_terminal_preconditions.py` suite remains red because its corpus-refusal test expects a structured manual part that is absent from the current bundled corpus; this step did not alter corpus material.
