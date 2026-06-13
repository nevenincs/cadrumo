---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` `P01.S03`

Verified M390 directory loading, registry integrity, annual IVA binding
behavior, application filing behavior, and file-size reduction after the split.

- Verified: `src/aeat/_data/registry/aeat/modelos/390`
- Verified: `src/aeat/domain/calculations/registry/test_modelo_390_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/application/filing/test_modelo_303_390.py`

## Description

M390 now loads through the generic directory-mode loader with one
fragment-directory revision. The split reduced the M390 review surface from an
808-line single file to 15 TOML fragments, with the largest fragment at 182
lines.

The broader verification gate surfaced a stale application test assumption:
`build_draft` tests for M303/M390 supplied no values for required bound
casilla bindings. The test now supplies explicit binding ids and scopes the
runtime schema provider to M303/M390, preserving the current registry contract
that bound casilla values flow through bindings.

Current registry file-size baseline:

- `390.toml` exists: false.
- M390 fragment count: 15.
- Largest M390 fragment: 182 lines.
- Largest remaining single-file modelo: M322 at 573 lines.

Remaining single-file modelos by line count:

- M322: 573
- M353: 569
- M184: 483
- M193: 472
- M309: 363
- M347: 356
- M360: 324
- M036: 297
- M840: 210
- M308: 194

## Tests

An initial broad pytest command failed because the application filing test did
not provide required bound-casilla bindings for M303/M390. The stale test was
updated and the full gate was rerun.

Validation completed:

- `uv run --no-sync pytest src/aeat/application/filing/test_modelo_303_390.py -q`
- `2 passed in 26.92s`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py::test_modelo_390_annual_iva_pipeline_resolves_binding_chain_from_four_303_filings src/aeat/application/calculations/test_binding_prefill.py::test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations src/aeat/application/filing/test_modelo_303_390.py -q`
- `129 passed in 124.76s`
