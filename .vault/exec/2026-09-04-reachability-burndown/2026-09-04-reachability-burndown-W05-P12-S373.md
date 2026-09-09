---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:97ad555023ab5195ede4f0ea61dfc7e3e0ffe994fe394cc9a145fd84feed07cf'
step_id: 'S373'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

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
