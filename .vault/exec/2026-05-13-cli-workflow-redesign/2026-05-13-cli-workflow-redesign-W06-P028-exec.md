---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W06.P028'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---

# `cli-workflow-redesign` `W06.P028`

Completed the de-shim and de-stub cleanup phase for central output rendering.

- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/core/errors/registry/_application.py`

## Description

Deleted the retained registry command `--json` parameters and removed the
CLI-local `JsonEncodingError` registry row after the core renderer became the
single owner of output encoding failures. File-output options that write
explicit report artifacts remain distinct from stdout rendering.

Closed plan rows: `W06.P028.S0163`, `W06.P028.S0164`,
`W06.P028.S0165`, `W06.P028.S0166`, `W06.P028.S0167`,
`W06.P028.S0168`.

## Tests

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_registry_cli.py -q`

`uv run --no-sync ruff check src/aeat/entrypoints/cli/registry.py src/aeat/core/errors/registry/_application.py`
