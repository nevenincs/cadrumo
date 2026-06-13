---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S120'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-018 for AEAT export deserialisation

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`
- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/constructs/0001-constructs.toml`
- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/formulas/0001-formulas.toml`
- `src/aeat/domain/calculations/registry/test_modelo_714_registry.py`
- `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

- Replace raw malformed wire-byte diagnostics with length plus short SHA-256 digest breadcrumbs.
- Wrap date, currency, and text decode failures as `AeatExportFormatError` so remote/export parse failures stay inside the AEAT error hierarchy without retaining raw stdlib exception chains.
- Remove divergent parsed values from multi-segment collision errors.
- Add malformed CURRENCY and RESERVED canary tests proving parser errors do not echo taxpayer-like bytes.
- Update date decode rejection tests to expect typed export-format errors.
- Re-run the broader export-format batch after the first focused closure uncovered registry drift and stale golden-output evidence.
- Keep Modelo 714 Phase-A registry data honest by removing invalid fake formula rows and asserting the current manual casilla baseline directly through registry loading.
- Refresh the Modelo 303 BOE golden hash only after grounding the changed bytes against the official DP30303 workbook rows for casillas 110, 78, and 87.
- Close `AFR-018` and `W12.P26.S120` in the active-profile rollout ledger.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_blank_input_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_inline_sign_blank_magnitude_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_currency_invalid_wire_bytes_raise_redacted_export_format_error src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_reserved_field_corruption_rejected_at_decode src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_reserved_field_corruption_error_redacts_wire_bytes src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py` passed: 38 passed.
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_modelo_151_registry.py` passed: 4 passed.
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_modelo_714_registry.py` passed: 4 passed.
- `uv run --no-sync ruff check src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/formulas/0001-formulas.toml src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/constructs/0001-constructs.toml src/aeat/domain/calculations/registry/test_modelo_714_registry.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_modelo_303_golden_sha_fichero_boe --tb=short` passed: 1 passed.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/_formats/test_record_spec.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_currency_edge_cases.py` passed: 114 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S120` closed the step row.

## Notes

- The initial broader run did expose real non-S120 blockers. They were not ignored: Modelo 151 now validates in the focused registry test, Modelo 714 no longer carries invalid placeholder formula metadata, and the Modelo 303 hash update is backed by explicit official-layout offset assertions rather than a hash-only update.
- The next affected-file row is `W12.P26.S121` for `_record_spec.py`.
