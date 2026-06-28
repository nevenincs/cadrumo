---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S121-S128'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-019 through AFR-026 for AEAT export/Sede/verify surfaces

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`
- `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`
- `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- `src/aeat/adapters/outbound/aeat/sede/_parse.py`
- `src/aeat/adapters/outbound/aeat/sede/_renta_web_open_safety.py`
- `src/aeat/adapters/outbound/aeat/verify/__init__.py`
- `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `.vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Description

- Classify `_record_spec.py` as fixed-width record metadata used by the exporter/deserialiser; it does not own remote mirror state or persistence.
- Confirm `_censo_live.py`, `_nif_iva_check.py`, `_renta_web_open_safety.py`, and `verify/__init__.py` remain authenticated read-only remote-provider boundaries guarded by `RemoteStateGuardPolicy`.
- Fix `_declarations.py` rather than merely classify it: the bbox declaration-PDF path now materialises sensitive PDF bytes through a private `mkstemp` fd, writes through that fd, closes before pdfplumber reopens the path, and unlinks on exit.
- Confirm `_observation_store.py` routes filed-declaration observations and artefacts through the active-bucket secure-object repository.
- Confirm `_parse.py` remains a pure HTML parser/plaintext-exception boundary with no storage backend.
- Enrol the new declaration-PDF temp bridge, the operator-enabled IVA wallet diagnostic summary writer, and the ECB maintenance refresh writer in the production write inventory with real behavior coverage.

## Outcome

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/_formats/test_record_spec.py src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py src/aeat/adapters/outbound/aeat/export/_formats/test_date_edge_cases.py src/aeat/adapters/outbound/aeat/export/_formats/test_currency_edge_cases.py` passed: 114 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/sede/test_no_write_surface.py src/aeat/adapters/outbound/aeat/sede/test_censo_live.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/test_observation_store.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/adapters/outbound/aeat/sede/test_parse.py src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_safety.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed: 155 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/browser/test_site_health.py src/aeat/adapters/outbound/aeat/browser/test_session.py` passed: 58 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/verify/test_verify.py` passed: 13 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed: 2 passed.
- Targeted Ruff passed over the S119-S128 source files plus the touched declaration, wallet diagnostic, and production write-inventory tests.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S121` through `W12.P26.S128` was attempted. The CLI closed S121-S123 but reported success without persisting S124-S128, so the five remaining affected-file register rows and step checkboxes were patched directly and rechecked.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the existing `PLAN022` monotonic-order warning only.

## Notes

- S123 was not a pure scanner false positive. The prior `NamedTemporaryFile(delete=False)` bridge was short-lived, but it still wrote sensitive PDF bytes as plaintext with weaker custody than the existing secure temp convention. The implementation now uses the project-standard private-fd pattern and has direct filesystem coverage.
- The IVA wallet diagnostic writer remains an explicit operator-enabled diagnostic surface, not runtime data persistence. Its real-browser test proves raw input values, wallet amounts, and table labels do not enter the written summary.
- The ECB writer is a maintenance utility for bundled official reference data, not taxpayer/application state. It is classified in the production write inventory because the inventory gate must account for all production writes, including non-sensitive reference refresh paths.
