---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S15'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P04.S15 - registry discovery application facade

Scope: move remaining registry authority query construction behind public application facades.

## Description

- Add `src/aeat/application/modelo/_registry_discovery.py` as the application-side registry discovery facade implementation.
- Export registry discovery functions from the public `aeat.application.modelo` package facade.
- Rewire `_modelo_discovery_cli.py` to call only public application package exports for list, describe, casillas, bindings, formulas, and registry modelo code enumeration.
- Rewire `_modelo.py` period-token validation to call `declared_modelo_period_tokens` from the public application package facade.
- Tighten the `_modelo.py` architecture guard budgets for direct registry authority reads and direct `RegistryQueryService` construction to zero.

## Outcome

CLI discovery modules now consume application-layer facade functions instead of constructing registry services or reading registry authority directly. Registry internals remain behind the application boundary, while the public package `__init__.py` is the consumer-facing export surface.

## Notes

Verification commands passed:

- `uv run --no-sync ruff check` over touched CLI and application files.
- `uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_discovery_cli.py src/aeat/application/modelo/_registry_discovery.py`
- `rg -n "resources\(\)\.modelos\.authority|RegistryQueryService" src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `rg -n "application\.modelo\._|\.\.\.application\.modelo\._" -g "_modelo*.py" src/aeat/entrypoints/cli`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q`

Both `rg` audits returned no CLI offenders. A RAG search for the discovery facade and no-registry-service-construction surface returned `_modelo_discovery_cli.py` as the relevant implementation surface.
