---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S120'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-018 for AEAT export deserialisation

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`
- `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

- Replace raw malformed wire-byte diagnostics with length plus short SHA-256 digest breadcrumbs.
- Wrap date, currency, and text decode failures as `AeatExportFormatError` so remote/export parse failures stay inside the AEAT error hierarchy without retaining raw stdlib exception chains.
- Remove divergent parsed values from multi-segment collision errors.
- Add malformed CURRENCY and RESERVED canary tests proving parser errors do not echo taxpayer-like bytes.
- Update date decode rejection tests to expect typed export-format errors.
- Close `AFR-018` and `W12.P26.S120` in the active-profile rollout ledger.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_blank_input_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_inline_sign_blank_magnitude_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_invalid_wire_bytes_raise_redacted_export_format_error src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_reserved_field_corruption_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_reserved_field_corruption_error_redacts_wire_bytes src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py` passed: 38 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S120` closed the step row.

## Notes

- A broader export-format run including `test_modelo_130_golden_sha_fichero_boe` and `test_modelo_303_golden_sha_fichero_boe` currently fails before reaching this deserialiser surface because registry validation rejects Modelo 151 legal refs. That is unrelated to S120 and remains outside this commit.
- The next affected-file row is `W12.P26.S121` for `_record_spec.py`.
