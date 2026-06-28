---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S299'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-core-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S299`

Closed the `core.locks` plaintext exception row.

## Changes

- Replaced silent best-effort `OSError` suppression in parent-directory fsync and lock release teardown with debug logging.

## Validation

- `uv run ruff check src/aeat/core/locks.py src/aeat/core/test_logging.py src/aeat/core/test_paths.py`
- `uv run pytest src/aeat/core/test_output_rendering.py src/aeat/core/test_logging.py src/aeat/core/test_paths.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`
