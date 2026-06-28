---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S261'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s261-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S261`

Closed stale `AFR-159` for absent application topics module.

## Description

- Verified `src/aeat/application/topics/__init__.py` is absent in the current tree.
- Confirmed active topic catalogue code has moved to `src/aeat/core/topics` and application registry code imports from `aeat.core.topics`.
- Left the deleted application module absent rather than reintroducing a deprecated application-layer topic surface.
- Reclassified `AFR-159` from `plaintext-exception` to `retired`.
- Closed `S261` through `vaultspec-core vault plan step check` and aligned the AFR register row.

## Outcome

`AFR-159` is closed as `retired`. No production code changed because the referenced affected file no longer exists; the secure-storage plan now reflects the relocated topic architecture instead of tracking a stale plaintext file.

Validation passed:

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
