---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-07-17'
body_hash: 'sha256:5e8e915ffbe953d8a133d662c5dfe4d075b098239824ca6008357d988a58f1b8'
step_id: 'S310'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-core-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S310`

Closed the `core.paths` plaintext exception row.

## Changes

- Confirmed `core.paths` is a validation-only containment boundary using `CoreValidationError` and strict path/token rejection.

## Validation

- `uv run ruff check src/aeat/core/paths.py src/aeat/core/test_paths.py`
- `uv run pytest src/aeat/core/test_paths.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`
