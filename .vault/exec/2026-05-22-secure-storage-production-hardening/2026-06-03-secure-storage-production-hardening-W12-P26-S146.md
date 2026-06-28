---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S146'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s146-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S146`

Closed `AFR-044` for storage provider boundary records.

## Description

- Reviewed `src/aeat/adapters/outbound/storage/_records.py` against the `remote-provider` scanner signal.
- Replaced stale record documentation that counted only provider records and omitted remote mirror manifest records.
- Removed the obsolete in-memory test backend reference from provider metadata documentation.
- Centralized repeated 64-character object HMAC, ciphertext hash, and storage revision identifier field shapes inside the records module.
- Reused those typed field shapes across remote mirror object manifests, namespace manifests, issue records, and revision ancestor IDs.
- Added a foundation test proving malformed remote mirror revision ancestor IDs are rejected by the Pydantic record boundary.
- Closed `W12.P26.S146` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-044` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_adverse_conditions.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/test_foundation.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n "Settings\\(|PROJECT_ROOT|os\\.environ|print\\(|typer\\.echo|# noqa|pragma|type: ignore|monkeypatch|_Fake|_Stub|skip\\(|xfail|except Exception|except BaseException" src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/test_foundation.py`

## Notes

The field-shape constants remain private to the records module. They centralize the current storage schema without expanding the public package surface in this step.
