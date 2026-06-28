---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W06.P027'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---

# `cli-workflow-redesign` `W06.P027`

Completed the shadow duplicate removal phase for central output rendering.

- Modified: `src/aeat/entrypoints/cli/_common.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`

## Description

Removed the CLI-local JSON serializer from `_emit` and routed emission through
the central core renderer. Removed command-local JSON rendering branches from
the retained mounted `app registry` command family so registry commands use the
root `--format` state instead of per-command switches.

Closed plan rows: `W06.P027.S0157`, `W06.P027.S0158`,
`W06.P027.S0159`, `W06.P027.S0160`, `W06.P027.S0161`,
`W06.P027.S0162`.

## Tests

`uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/entrypoints/cli/test_registry_cli.py -q`

`rg -n -e "--json|json_output_requested|emit_json_success|typer\\.echo\\(.*model_dump_json|json\\.dumps|render_report_json|_emit_metric" src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_review.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_common.py`
