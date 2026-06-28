---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S56'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S56 - resolve undefined modelo envelope emitter reference

Scope: Wave `W05`; Phase `W05.P16`; Step `S56`.

## Description

- Verified the shifted modelo CLI decomposition resolves the undefined envelope emitter reference by importing `_emit_envelope` from `._common` inside extracted modelo command modules.
- Kept extracted modules independent from the legacy `_modelo.py` root by registering commands through explicit dependency injection for shared CLI helpers.
- Added static CLI decomposition and size-budget guardrails for extracted modelo command modules.

## Outcome

The S56 envelope-emitter defect is closed. The modelo CLI app imports, command registration succeeds, and extracted command modules no longer need to reach back into `_modelo.py` for envelope emission.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_export_cli.py src/aeat/entrypoints/cli/_modelo_readiness_cli.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py src/aeat/entrypoints/cli/_modelo_work_runs_cli.py src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py`
- `uv run --no-sync python -c "from aeat.entrypoints.cli._modelo import app; names=[c.name for c in app.registered_commands]; groups=[g.name for g in app.registered_groups]; print(names); print(groups)"`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_export_verb.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py -q`

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py -q` passes the architecture guard and the command-size guard, but the module-size guard currently fails on unrelated dirty live-IVA WIP in `src/aeat/entrypoints/cli/_app_live.py` (`2135` working-tree lines versus budget `2117`). Clean HEAD for `_app_live.py` is below that budget, so the failure is tracked as a shared-worktree residual for the W05.P17 full quality-audit baseline rather than hidden in S56.
