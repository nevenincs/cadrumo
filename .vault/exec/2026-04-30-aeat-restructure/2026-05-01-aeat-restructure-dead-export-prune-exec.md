---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-summary-exec]]"
---

# `aeat-restructure` `phase-post` `dead-export-prune`

Pruned dead exports from `__all__` across `src/aeat/`. A dead export is a name
listed in `__all__` with zero non-test importers (neither in `src/aeat/` nor
in `tests/`).

## Description

Scanned all `src/aeat/` Python files with `__all__` declarations. For
each exported name: verified external importers via substring search. Where
a name had zero external importers, it was removed from `__all__`. Where the
definition also had zero in-file callers, the definition was deleted.

Files where only `__all__` was trimmed (definition kept — still used internally):

- `src/aeat/adapters/inbound/borrador/_tarifa.py` — `TarifaFinding`
- `src/aeat/adapters/inbound/declaracion/_parsers/modelo_100/_scanner.py` — `HEADER_FORWARD_CIDS`
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` — `AEAT_CLAVE_MOVIL_SIDECAR_SCHEMA_VERSION`
- `src/aeat/adapters/outbound/aeat/export/_formats/_ingest.py` — `IngestSourceMeta`
- `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py` — `HeaderValue`
- `src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py` — `KentProfile`
- `src/aeat/domain/financial/transactions/_repository.py` — `DirectionResolver`
- `src/aeat/domain/formulas/_rulesets/_common.py` — `currency_casilla`, `round2`
- `src/aeat/domain/formulas/_rulesets/_mutators.py` — `PercentRateLocation`
- `src/aeat/domain/formulas/_rulesets/modelo_100/_ccaa.py` — 17 `TARIFA_*` constants
- `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py` — `LIS_CONSULT_2026_02_28_URL`, `RIRPF_CONSULT_2026_02_28_URL`
- `src/aeat/domain/formulas/_rulesets/modelo_100/_minimos.py` — 13 `MINIMO_*` constants
- `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_g_2024.py` — `TARIFA_ESTATAL_AHORRO_2024`
- `src/aeat/domain/profile/assets/__init__.py` — 6 names
- `src/aeat/domain/profile/inventory/__init__.py` — 4 names
- `src/aeat/domain/rental/_amortization_ledger.py` — `DAYS_PER_YEAR`
- `src/aeat/domain/rental/_anexo_c_aggregator.py` — 3 rate constants
- `src/aeat/domain/rental/_tier_resolver.py` — 4 constants
- `src/aeat/entrypoints/cli/_errors.py` — `command_error_boundary`
- `src/aeat/entrypoints/cli/audit/__init__.py` — `rulesets_app`
- `src/aeat/entrypoints/cli/financial/__init__.py` — `profile_app`
- `src/aeat/entrypoints/cli/workflow/_helpers.py` — `EngineFactory`

Files where definition was also deleted (no in-file callers):

- `src/aeat/adapters/inbound/declaracion/_extract.py` — `LabelExtractionHit` import alias
- `src/aeat/domain/financial/vat/_catalogue.py` — `total_citation_count` function
- `src/aeat/domain/financial/vat/_rates.py` — `total_rate_count` function
- `src/aeat/domain/formulas/_rulesets/_mutators.py` — `MutationCase` class, `build_percent_rate_mutants`, `build_scalar_mutants`
- `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py` — 8 dead URL constants
- `src/aeat/domain/normatives/__init__.py` — `NORMATIVE_CATALOGUE`
- `src/aeat/domain/testing/_schema.py` — `SYNTHETIC_COMMENT_REQUIRED_SUBSTRING`

Edge cases preserved:

- `LIRPF_CONSULT_2026_02_28_URL` in `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py`
  kept in `__all__` — imported externally by `anexo_n_2025.py`
- `PercentRateLocation` in `src/aeat/domain/formulas/_rulesets/_mutators.py`
  kept defined — used internally by `classify_percent_rate`

Import-sort fix applied to `src/aeat/entrypoints/cli/submission/export.py`
(sibling-agent change introduced unsorted import block, flagged by ruff).

## Tests

`uv run pytest --collect-only -q` collected 6799/6819 tests with no import errors.
`ruff check src/aeat/` passes clean (excluding pre-existing sibling-agent corruption
in `src/aeat/core/identity/test_tax_id.py` which is out of scope).
