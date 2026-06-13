---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S313'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-resource-boundary-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S313`

Closed the `StaticModeloRepository` plaintext exception row.

## Changes

- Narrowed the modelo lookup failure wrapper to `RegistrySnapshotError`, preserving registry load/validation/backend failures as their original typed AEAT errors.

## Validation

- `uv run pytest src/aeat/core/resources/_repos/test_modelos.py src/aeat/core/resources/test_registry.py -q`
