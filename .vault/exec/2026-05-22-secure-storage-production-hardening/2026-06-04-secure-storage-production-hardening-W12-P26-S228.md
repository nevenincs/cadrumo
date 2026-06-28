---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S228'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s228-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S228`

Closed `AFR-126` for the live expedientes snapshot service.

## Description

- Reviewed `src/aeat/application/live/_expedientes.py` against the
  `remote-mirror` classification for secure-object, manifest-bucket, and
  remote-provider signals.
- Verified expedientes snapshots are read-only AEAT-origin mirror records
  stored through `secure_object_repository_for_bucket()` and the live
  expedientes secure-object namespace.
- Localized blank bucket id, blank snapshot id, not-found, and ambiguous-prefix
  refusal paths for the expedientes surface.
- Hardened lookup refusals so ambiguous-prefix errors expose match count rather
  than matched full snapshot ids.
- Updated real-runtime expedientes tests to assert secure-object persistence,
  raw SQLite non-leakage for the expediente id witness, legacy JSONL absence,
  locale metadata, and bounded error context.
- Closed `S228` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-126` is closed as `remote-mirror`. Expedientes durable state remains an
encrypted bucket-local mirror of the authenticated AEAT read surface, and the
reviewed refusal boundaries now follow the locale-backed error convention.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/live/_expedientes.py src/aeat/application/live/test_expedientes.py`
- `uv run --no-sync pytest -q src/aeat/application/live/test_expedientes.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "expedientes or s85_runtime"`
- `uv run --no-sync python -m aeat.locales audit`

## Notes

Locale catalogue updates were performed through `python -m aeat.locales`
(`set` and `audit`). No naked environment access, settings bypass, silent
exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced.
