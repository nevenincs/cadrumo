---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:23088f446d8c5b0bb696795eceefe88adb187b231c436537bcffdeb397c7ba14'
step_id: 'S246'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the disconnected fincas domain and persistence slice whose source-readiness owner is permanently false and which no product acquisition, calculation, or presentation path reaches.

## Scope

- `Remove domain models and calculations`
- `persistence adapter and ORM tables`
- `synthetic and census-only tests`
- `dormant error registrations and locale leaves`
- `preserve generic detector teeth`
- `amend stale architectural evidence`
- `run focused storage and registry gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes


- `D` `src/cadrumo/domain/fincas/__init__.py`
- `D` `src/cadrumo/domain/fincas/aggregates.py`
- `D` `src/cadrumo/domain/fincas/amortization_ledger.py`
- `D` `src/cadrumo/domain/fincas/enums.py`
- `D` `src/cadrumo/domain/fincas/errors.py`
- `D` `src/cadrumo/domain/fincas/expense_rollup.py`
- `D` `src/cadrumo/domain/fincas/imputacion_parameters.py`
- `D` `src/cadrumo/domain/fincas/models.py`
- `D` `src/cadrumo/domain/fincas/repository_ports.py`
- `D` `src/cadrumo/domain/fincas/source_readiness.py`
- `D` `src/cadrumo/domain/fincas/tier_resolver.py`
- `D` `src/cadrumo/domain/fincas/titularidad.py`
- `D` `src/cadrumo/domain/fincas/tests/__init__.py`
- `D` `src/cadrumo/domain/fincas/tests/test_aggregates.py`
- `D` `src/cadrumo/domain/fincas/tests/test_amortizacion_rate_registry_grounded.py`
- `D` `src/cadrumo/domain/fincas/tests/test_amortization_ledger.py`
- `D` `src/cadrumo/domain/fincas/tests/test_expense_rollup.py`
- `D` `src/cadrumo/domain/fincas/tests/test_imputacion_parameters.py`
- `D` `src/cadrumo/domain/fincas/tests/test_imputacion_regime.py`
- `D` `src/cadrumo/domain/fincas/tests/test_rehab_lookback_is_calendar_relative.py`
- `D` `src/cadrumo/domain/fincas/tests/test_threshold_registry_grounded.py`
- `D` `src/cadrumo/domain/fincas/tests/test_tier_resolver.py`
- `D` `src/cadrumo/domain/fincas/tests/test_titularidad_attribution.py`
- `D` `src/cadrumo/adapters/persistence/profile/fincas.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/_fincas_engine_fixture.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_fincas_repository.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_fincas_roundtrip_anti_tautology.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/orm.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part2.py`
- `M` `src/cadrumo/domain/tests/regulatory_cap_witnesses.py`
- `M` `src/cadrumo/domain/iva/tests/test_legal_basis_rate_grounding.py`
- `M` `src/cadrumo/domain/iva/recargo_equivalencia.py`
- `M` `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`
- `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `M` `src/cadrumo/core/external_constants.py`
- `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `.vault/audit/2026-07-12-rental-income-hardening-audit.md`
- `M` `.vault/reference/2026-09-02-unreachable-capability-disconnected-capability-inventory-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused S246 paths>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" <focused regulatory, error, schema, IVA, and SQL suites>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`


## Notes

The exact zero-target detector remains red on the live backlog. This coherent withdrawal reduced unreachable modules from 47 to 34, orphaned tests from 4 to 0, and exact unused symbols from 295 to 292. Focused verification passed 229 tests. The wider external-constant file also exposed two peer-owned failures caused by an unparseable dirty `domain/contribuyente/assets/__init__.py`; the S246-specific tests pass when selected directly.
