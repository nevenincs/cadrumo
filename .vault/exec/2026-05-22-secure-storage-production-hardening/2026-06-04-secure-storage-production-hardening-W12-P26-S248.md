---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S248'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s248-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S248`

Closed `AFR-146` for the review source adapter boundary.

## Description

- Reviewed `src/aeat/application/review/_adapters.py` as a manifest-discovery/read-model adapter surface.
- Verified transaction, invoice, and filing draft sources are loaded through their domain repositories and active-profile/bucket runtime paths.
- Verified the adapters do not write review state or persist sidecar plaintext files.
- Removed raw backend exception text from transaction, invoice, and filing draft source-load error messages and context.
- Added real secure-object corruption tests for invoice and filing-draft adapter load failures.
- Added the missing localized filing-draft source-load error key through the canonical locale CLI.
- Closed `S248` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-146` is closed as `manifest-discovery` with `active-profile, manifest-bucket` signals. The adapters remain read-only source projections and now expose only non-sensitive error type metadata when secure backend load failures are wrapped for the review boundary.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/review/_adapters.py src/aeat/application/review/test_adapters.py`
- `uv run --no-sync pytest -q src/aeat/application/review/test_adapters.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The invoice and draft load-failure tests write malformed payload bytes through the real active-bucket secure-object repositories, not through fake repositories or monkeypatches.
