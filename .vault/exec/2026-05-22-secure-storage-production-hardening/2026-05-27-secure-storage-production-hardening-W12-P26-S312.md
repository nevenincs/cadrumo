---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S312'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-resource-boundary-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S312`

Closed the `LegalParameterRepository` plaintext exception row.

## Changes

- Confirmed legal parameter reads route through the bundled registry loader and the central resource repository cache.

## Validation

- `uv run pytest src/aeat/core/resources/_repos/test_singletons.py src/aeat/core/resources/test_registry.py -q`
