---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S206'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s206-review-audit]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S206`

Closed `AFR-104` for application tabular export serialization.

## Description

- Reviewed `src/aeat/application/export/_tabular.py` against the
  `plaintext-exception` classification for caller-directed export payloads.
- Regrounded the row against the 2026-06-03 modelo export evidence and workbook
  parity ADRs to avoid claiming modelo workbook, evidence, or official-layout
  parity from this generic serializer slice.
- Replaced the remaining bare SHA-256 validation `ValueError` with the existing
  core-derived `ExportFieldError` and localized refused-export-field key.
- Added a real XLSX readback test that loads the serialized workbook bytes and
  asserts row content plus returned metadata.
- Cross-committed intersecting live-read constants work already present in the
  same core constants files: typed pre303 browser-action labels in the external
  constants schema/TOML and the IVA compensation wallet own-name representation
  HTML guard consumed by those constants.
- Removed deprecated standalone diagnostics CLI locale leaves through
  `python -m aeat.locales` and dropped their stale locale inventory ratchet after
  confirming the `src/aeat/diagnostics` package is absent.
- Closed the plan step through the vaultspec CLI and aligned the AFR register
  entry with the recorded closure.

## Outcome

`AFR-104` is closed as a bounded plaintext exception. The module remains pure
in-memory serialization with no direct storage, settings, environment, active
profile, SQL, or secure-object repository access. Export validation failures now
carry the project export exception in the pydantic validation context instead of
a naked standard-library validation error.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/export/_tabular.py src/aeat/application/export/test_tabular.py`
- `uv run --no-sync pytest src/aeat/application/export/test_tabular.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/application/export/_tabular.py src/aeat/application/export/test_tabular.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -k "browser_action or representation_own_name or own_name_representation or wallet"`
- `uv run --no-sync pytest -q src/aeat/application/export/test_tabular.py src/aeat/core/test_external_constants.py -k "export or mime_type or tabular or pre303 or live_safety"`
- `uv run --no-sync pytest -q src/aeat/test_locale_coverage_inventory.py src/aeat/locales/test_parity.py -k "operator_error_locale_key or codebase_to_locale_parity"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The XLSX bytes are still an explicit operator export payload, not secure
persistence. No production file writes, direct `SecureObjectRepository`
construction, naked environment access, silent exception swallowing, raw
user-facing error string, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced. Intersecting live-read constants work was
validated as part of the cross-commit because it shares the same core constants
files. Deprecated diagnostics locale leaves were removed only through the
canonical `aeat.locales` CLI.
