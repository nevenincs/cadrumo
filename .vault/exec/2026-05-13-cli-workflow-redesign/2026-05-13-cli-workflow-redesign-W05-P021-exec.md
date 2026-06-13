---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W05.P021'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
---



# `cli-workflow-redesign` `W05.P021`

Completed the backend implementation phase for root help and discovery
behavior.

- Created: `src/aeat/application/operator_surface/_help.py`
- Modified: `src/aeat/application/operator_surface/_models.py`
- Modified: `src/aeat/application/operator_surface/__init__.py`

## Description

Added backend-owned Pydantic contracts for help documents, help sections,
entries, help surfaces, and root landing reports. Added application functions
that build curated help documents for root, config, and app surfaces from the
accepted operator surface contract and mounted command family inventory.

The backend service lists only currently mounted accepted command families.
It does not invent planned command names and does not encode business behavior
in the CLI package. Bare-root landing text is derived from caller-provided
profile state and remains presentation-only.

Closed plan rows: `W05.P021.S0121`, `W05.P021.S0122`,
`W05.P021.S0123`, `W05.P021.S0124`, `W05.P021.S0125`,
`W05.P021.S0126`.

## Tests

`uv run --no-sync pytest src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_root_help_shape.py -q`

`uv run --no-sync ruff check src/aeat/application/operator_surface src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_config.py src/aeat/entrypoints/cli/test_root_help_shape.py`
