---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:a323e1e8bb760d84c60ed97f7cc5088b192141404f6154802c8d46c73bbca887'
step_id: 'S172'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production stub-modelo census and the M210 engine-live rollout switch, route AEAT modelos to their capability-owning registry/readiness/calculation/filing boundaries, retain only the domain-grounded ceded-autonomic redirect, amend the contradicted authorization ADR, and add an aggregated production-metastate detector with teeth for both removed shapes.

## Scope

- `src/cadrumo/application/modelo/work_create_policy.py`
- `src/cadrumo/core/config.py`
- `focused CLI tests and locale catalogues`
- `dev/quality/production_metastate.py and detector tests`
- `quality suite and justfile aggregation`
- `modelo-multiyear-renta ADR`
- `reachability burndown reference`
- `locale audit`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/application/modelo/work_create_policy.py`
- `M` `src/cadrumo/core/config.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `dev/locales/tests/test_parity.py`
- `A` `dev/quality/production_metastate.py`
- `A` `dev/quality/tests/test_production_metastate.py`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `M` `.vault/adr/2026-06-02-modelo-multiyear-renta-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "STUB_MODELO_LOCALE_KEYS|STUB_ONLY_MODELOS|cadrumo_m210_engine_live|create_stub_modelo_(151|210|714|721)_refused" src/cadrumo -g "*.py" -g "*.yml"` -> `pass`
- `verify:` `uv run ruff check <S172 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 -m integration src/cadrumo/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py` -> `pass` (8 passed)
- `verify:` `uv run pytest -q dev/quality/tests/test_production_metastate.py dev/quality/tests/test_suite_gate_table.py` -> `pass` (12 passed)
- `verify:` `uv run python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run python -m dev.locales audit` -> `fail`
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail`
- `verify:` `uv run pytest -q -n0 -m integration src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py -k "m210_work_create"` -> `fail`

## Notes

The locale audit retains the pre-existing drift in each of ca, en, es, and hu: missing `tui.declarations.lifecycle.verification_refused` and extra `aggregation.source_mesh.errors.ambiguous_source_disposition`. The live detector remains at 360 exact symbols and 18 orphan test modules; the removed metastate declarations were not live-signal rows. The focused M210 readiness test fails before reaching the changed guard because its process-scoped test login leaves `read_profile_bucket(_PROFILE_ID)` absent on this host; the direct guard proof in the eight-test integration module passes and establishes that M210 and the other former AEAT census members are admitted. Existing unrelated shared edits in the overlapping config, locale, suite, justfile, and CLI-test paths were preserved.
