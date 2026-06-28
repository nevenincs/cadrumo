---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S311'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-resource-boundary-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S311`

Closed the `core.resources._boundary` plaintext exception row.

## Changes

- Confirmed the boundary is read-only package-resource access through `importlib.resources`, not a secure storage bypass.
- Updated resource tests to use the current directory-mode Modelo 036 manifest path.

## Validation

- `uv run pytest src/aeat/core/test_resources.py src/aeat/core/resources/test_registry.py -q`
