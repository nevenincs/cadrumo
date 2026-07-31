---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:cd4d3dc1c3aa342432d1dd3a6f994bc164d586a9d45e57bb4e857eb593b22a3c'
step_id: 'S84'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S84 Core Config Verification

Scope: verify core config behavior and facade imports after decomposition.

## Description

- Ran Ruff over `config.py`, `_config_storage_route.py`, and focused config tests.
- Ran focused core config, release config, and config CLI tests.
- Smoke-tested public facade imports for route classification, bucket settings derivation, and settings loading.

## Outcome

Verification passed. Public consumers still import from `aeat.core.config`; the storage-route implementation is now behind the facade.

## Notes

Evidence: 42 focused tests passed; Ruff passed; `config.py` measured 1275 lines and `_config_storage_route.py` measured 75 lines.
