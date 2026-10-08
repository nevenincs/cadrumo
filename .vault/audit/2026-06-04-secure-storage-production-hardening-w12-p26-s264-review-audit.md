---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:d277406eef022ea2465f03e3577878e13c86c79a68e15f2c124327a600b8abb3'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S264` Review

## S264-001 | MEDIUM | Blank bucket refusal bypassed localization

The retired module raised `CensoSyncError("bucket_id must not be blank")` directly. The exception type was correct, but the message was not enrolled in the translation catalogue.

Disposition: fixed. The refusal now carries `errors.censo.bucket_id_blank`, with locale entries added through `aeat.locales`.

## S264-002 | MEDIUM | Censo ratio parse failures were silently swallowed

Both the apply-time home-office seeding path and the read-only ratio binding path caught `InvalidOperation` and `ValueError` and returned empty results without any diagnostic trace. Under malformed remote censo payloads this made the drop invisible.

Disposition: fixed. The shared ratio parser now logs debug diagnostics for non-decimal censo values and invalid ratio bounds, without logging the raw remote values.

## S264-003 | LOW | Censo error docstring referenced a deprecated profile command

The retired module still referenced `aeat config profile init`. The current operator surface is `aeat config profile create`.

Disposition: fixed.

## S264-004 | PASS | Validation

- the historical check
- the historical check
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-162`.
