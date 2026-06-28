---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---



# Domain registry plaintext-exception closeout audit

## Scope

This closeout covers W12.P26.S334, W12.P26.S341, W12.P26.S344, W12.P26.S345, and W12.P26.S352.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S334 | AFR-232 | `categories._registry` | accepted plaintext exception |
| W12.P26.S341 | AFR-239 | `fincas._imputacion_parameters` | accepted plaintext exception |
| W12.P26.S344 | AFR-242 | `iva._catalogue` | accepted plaintext exception |
| W12.P26.S345 | AFR-243 | `iva._rates` | accepted plaintext exception |
| W12.P26.S352 | AFR-250 | `manuals.errors` | accepted plaintext exception |

## Findings

- The category, fincas, IVA catalogue, and IVA rate modules are read-only loaders over bundled registry authority data. They use the central bundled-resource boundary for default path resolution and do not persist profile aggregates, ledger records, filing state, sessions, secrets, or remote mirror payloads.
- Category and IVA user-facing registry text remains wrapped in `tr()` where the loaded registry field is intended for display. The VAT-rate loader exposes numeric/legal records and has no UI string surface.
- Category and IVA missing-file preflight failures now wrap `stat()` failures into domain AEAT exceptions instead of leaking builtin `OSError`.
- LIRPF art. 85 parameter drift now raises `FincaValidationError` for missing or unparsable registry constants instead of leaking builtin `KeyError` or raw parse exceptions.
- Manual error taxonomy remains exception-only and derives from the core AEAT exception hierarchy with central registry coverage.

## Closeout Rationale

These plaintext reads are accepted because they are committed authority registries and exception definitions, not mutable secure storage. Their role is to validate and expose legal/corpus metadata. Runtime user data must still flow through the secure storage architecture and profile-bound repositories.

## Validation

- `uv run ruff check src/aeat/domain/categories/_registry.py src/aeat/domain/categories/test_registry.py src/aeat/domain/fincas/_imputacion_parameters.py src/aeat/domain/fincas/test_imputacion_parameters.py src/aeat/domain/iva/_catalogue.py src/aeat/domain/iva/_rates.py src/aeat/domain/iva/test_catalogue_period_keyed.py src/aeat/domain/iva/test_rates.py src/aeat/domain/manuals/errors.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_verify.py`
- `uv run pytest src/aeat/domain/categories/test_registry.py src/aeat/domain/categories/test_profile.py src/aeat/domain/fincas/test_imputacion_parameters.py src/aeat/domain/iva/test_catalogue_period_keyed.py src/aeat/domain/iva/test_rates.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_verify.py -q`
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Safety Notes

- No deprecated config-init command surface was introduced.
- No `pragma` or `noqa` suppression was added.
- No environment handling was added; default data paths still route through bundled resources.
- No test was added that uses fake, stub, monkeypatch, skip, xfail, or mirrored business logic.
