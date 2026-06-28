---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W05.P023'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
---



# `cli-workflow-redesign` `W05.P023`

Completed the de-shim and de-stub cleanup phase for root help and discovery
behavior.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_config.py`
- Modified: `src/aeat/entrypoints/cli/test_root_help_shape.py`

## Description

Removed Typer's generic root/config/app help behavior from the curated
operator entry points and replaced it with backend-owned help documents.
The root, config, and app surfaces now render only accepted workflow guidance
for the current command tree. The implementation does not add alias commands,
compatibility routes, or placeholder surfaces.

Closed plan rows: `W05.P023.S0133`, `W05.P023.S0134`,
`W05.P023.S0135`, `W05.P023.S0136`, `W05.P023.S0137`,
`W05.P023.S0138`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync ruff check src/aeat/application/operator_surface src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/test_root_help_shape.py`
