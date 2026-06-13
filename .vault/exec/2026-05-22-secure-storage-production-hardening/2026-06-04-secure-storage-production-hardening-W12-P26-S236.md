---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S236'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s236-review-audit]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S236`

Closed `AFR-134` for the modelo fichero-BOE export service.

## Description

- Reviewed `src/aeat/application/modelo/_export.py` against the secure-storage
  affected-file register, source-neighbor searches, and the accepted 2026-06-03
  modelo export evidence/workbook/visual ADRs.
- Reclassified the row from `manifest-discovery` to `plaintext-exception`
  because the service intentionally writes an operator-selected local
  fichero-BOE artefact while routing bucket events through repositories.
- Localised export refusal paths through `python -m aeat.locales set`.
- Updated export tests to assert translated-message keys and structured context
  instead of raw English substrings.
- Hardened temporary export cleanup so `.tmp` deletion failures are debug-logged
  through the project logger without masking the original draft-write or
  bucket-event failure.
- Closed `S236` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-134` is closed as `plaintext-exception`. The module still does not contact
AEAT or select a secure-object backend directly; it writes the explicit export
file requested by the operator and appends the corresponding bucket event through
the repository boundary.
Temporary-file cleanup is best-effort and redacted: cleanup failures log the
stage and exception type, not the operator-selected filesystem path, and the
original export failure remains the raised root cause.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/modelo/test_export.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

Locale catalogue leaves were updated exclusively through the canonical
`aeat.locales` CLI. No settings bypass, naked environment access, monkeypatch,
fake, mock, skip, xfail, duplicate export builder, or tautological test was
introduced. Workbook parity/evidence/visual export builder obligations remain
owned by their accepted ADR workstreams.
