---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `scenario-parity-harness`

Added and restored a manual-first scenario/tape parity harness so registry
calculation checks can be stored, replayed, and compared against the current
runtime.

- Created: `src/aeat/domain/calculations/registry/_parity_tapes.py`
- Created: `src/aeat/domain/calculations/registry/test_parity_tapes.py`
- Created: `src/aeat/entrypoints/cli/test_registry_parity_cli.py`
- Updated: `src/aeat/domain/calculations/registry/__init__.py`
- Updated: `src/aeat/entrypoints/cli/registry.py`
- Updated: `src/aeat/locales/en.yml`
- Updated: `src/aeat/locales/es.yml`
- Updated: `src/aeat/locales/ca.yml`
- Updated: `src/aeat/locales/hu.yml`

## Description

The new harness defines a strict parity scenario model, stores each run as a
tape, and replays archived tapes against the current registry implementation.
Scenario workbook paths are resolved relative to the archived scenario source
when needed, and tape replay compares stable calculation fields while ignoring
volatile execution timing.

The registry package now exports the parity scenario/tape API, and the registry
CLI exposes a dedicated `parity` command group with `run` and `replay` commands.
`run` executes a stored scenario, archives the resulting tape, and can emit JSON
or text metrics. `replay` reloads a stored tape and re-runs the scenario against
the current calculation path so manual parity work can detect drift.

The new tests cover scenario JSON round-trip, tape save/load, replay stability,
and the CLI command surface. Locale parity was updated so the new command help
strings remain translation-complete.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_parity_tapes.py -q`
  passed.
- `uv run pytest src\aeat\entrypoints\cli\test_registry_parity_cli.py -q`
  passed.
- `uv run pytest src\aeat\entrypoints\cli\test_registry_cli.py src\aeat\locales\test_parity.py -q`
  passed.
- `uv run ruff check src\aeat/domain/calculations/registry/_parity_tapes.py src\aeat/domain/calculations/registry/__init__.py src\aeat/domain/calculations/registry/test_parity_tapes.py src\aeat/entrypoints/cli/registry.py src\aeat/entrypoints/cli/test_registry_parity_cli.py`
  passed.
- `uv run ty check src\aeat/domain/calculations/registry/_parity_tapes.py src\aeat/domain/calculations/registry/__init__.py src\aeat/domain/calculations/registry/test_parity_tapes.py src\aeat/entrypoints/cli/registry.py src\aeat/entrypoints/cli/test_registry_parity_cli.py`
  passed.
- `uv run pytest src\aeat\locales\test_parity.py -q`
  passed.
- `git diff --check`
  passed.
