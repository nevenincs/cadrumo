---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S235'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s235-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S235`

Closed `AFR-133` for the Modelo 100 borrador binding resolver.

## Description

- Reviewed `src/aeat/application/modelo/_borrador_binding.py` against the
  secure-storage affected-file register, delegated live borrador repository,
  source-mesh degradation helper, and existing borrador binding tests.
- Reclassified `AFR-133` from manifest-only discovery to `remote-mirror`
  because the resolver constructs `Borrador100SnapshotRepository(bucket_id=...)`
  when no repository is injected, and that repository persists FINANCIAL
  `Envelope[Borrador100Snapshot]` records through the runtime secure-object
  backend.
- Localised user-facing borrador binding refusals for unsupported modelo,
  snapshot load failure, forbidden bindings, bucket/axis mismatches, registry
  mismatch, and decimal coercion failure through `python -m aeat.locales set`.
- Updated tests to assert translated-message keys and structured context rather
  than raw English message fragments.
- Closed `S235` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-133` is closed as `remote-mirror` with signals `secure-object,
manifest-bucket, remote-provider`. The module performs no direct environment
reads, plaintext side-store writes, or encryption-key handling; it delegates
durable storage to the live borrador snapshot repository and returns typed
calculation-source results. Storage classification, version, or decryption
degradation is surfaced through the shared source-mesh diagnostic path instead
of being swallowed.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/modelo/test_borrador_binding.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "borrador or s85_runtime"`
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S235`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Locale catalogue leaves were updated through the canonical `aeat.locales` CLI.
The previous plan disposition under-declared this file as `manifest-discovery`.
That was corrected in the affected-file register and step text before closeout.
No monkeypatch, fake, mock, skip, xfail, naked environment access, settings
bypass, or tautological test was introduced.
