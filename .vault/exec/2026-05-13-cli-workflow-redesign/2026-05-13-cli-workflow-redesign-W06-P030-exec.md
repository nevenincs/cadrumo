---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W06.P030'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---

# `cli-workflow-redesign` `W06.P030`

Completed the thin CLI exposure phase for central output rendering.

- Modified: `src/aeat/entrypoints/cli/_common.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`

## Description

Kept CLI command handlers as argument parsing and backend delegation surfaces.
Registry handlers now build typed backend reports, construct text lines, and
pass both to `_emit`; `_emit` delegates rendering to the core service using the
root `--format` state. No registry handler owns JSON serialization or
command-local output mode selection.

Closed plan rows: `W06.P030.S0175`, `W06.P030.S0176`,
`W06.P030.S0177`, `W06.P030.S0178`, `W06.P030.S0179`,
`W06.P030.S0180`.

## Tests

`uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/entrypoints/cli/test_registry_cli.py -q`

`uv run --no-sync ruff check src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py src/aeat/entrypoints/cli/_common.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_registry_cli.py`
