---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
---



# `aeat-cli-hardening` `W5 Registry Query` `Modelo Introspection`

Closed the first registry-backed modelo introspection slice.

- Created: `src/aeat/domain/calculations/registry/_queries.py`
- Created: `src/aeat/domain/calculations/registry/test_queries.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Created: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Modified: `2026-05-08-aeat-cli-hardening-plan.md`

## Description

The domain registry now exposes typed query reports for modelo inventory,
modelo description, casillas, bindings, and formulas. The CLI registers
`aeat app modelo list`, `describe`, `casillas`, `bindings`, and `formulas`,
and delegates all registry reading to that query service.

The implementation also records the remaining profile-aware filtering gap as a
tracked discovered item. Applicability must be driven by the hardened
user-profile enrollment facts, not guessed in the CLI.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/test_user_cli_surface.py -k "query_service or parse_modelo_period or modelo_introspection or app_surface"`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ruff format --check src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/__init__.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_queries.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/__init__.py`
- `uv run --no-sync aeat app modelo list --year 2026`
- `uv run --no-sync aeat --format json app modelo describe 303 --period 2026Q1`
- `uv run --no-sync aeat app modelo bindings 130 --period 2026Q1`

All verification commands passed.
