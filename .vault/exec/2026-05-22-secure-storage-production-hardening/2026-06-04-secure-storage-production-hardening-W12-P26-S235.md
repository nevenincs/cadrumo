---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S235'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s235-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S235`

Closed `AFR-133` for the Modelo 100 borrador binding resolver.

## Description

- Reviewed `src/aeat/application/modelo/_borrador_binding.py` against the
  secure-storage affected-file register, source-neighbor searches, and existing
  borrador binding tests.
- Used vaultspec RAG semantic searches to confirm storage ownership remains in
  the live borrador snapshot repository while `_borrador_binding.py` owns the
  calculation binding decision and source-mesh adapter.
- Localised user-facing borrador binding refusals for unsupported modelo,
  snapshot load failure, forbidden bindings, bucket/axis mismatches, registry
  mismatch, and decimal coercion failure through `python -m aeat.locales set`.
- Updated tests to assert translated-message keys and structured context rather
  than raw English message fragments.
- Closed `S235` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-133` is closed as `manifest-discovery`. The module still performs no direct
environment reads, plaintext side-store writes, or secure-object backend
selection; it consumes the live repository interface and returns typed
calculation-source results.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/modelo/test_borrador_binding.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Locale catalogue leaves were updated through the canonical `aeat.locales` CLI.
A PowerShell quoting error during the first CLI attempt inserted a control
character into two transient locale values; those values were repaired and then
re-written through the CLI without backticks. No monkeypatch, fake, mock, skip,
xfail, naked environment access, settings bypass, or tautological test was
introduced.
