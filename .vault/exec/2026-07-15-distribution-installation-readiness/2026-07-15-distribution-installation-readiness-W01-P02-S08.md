---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S08'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Resolve the CLI subprocess from the MCP server installation instead of ambient PATH

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`

## Description

- Resolve the sibling `aeat` console script from the running interpreter's installation scripts directory.
- Use the resolved absolute executable for every supervised MCP command and bulk-resource resolver.
- Refuse incomplete installations with a structured error instead of consulting ambient `PATH`.

## Outcome

- The MCP subprocess path is now bound to the same Python environment as `cadrumo-mcp`.
- A real `contract` command completed with `PATH` reduced to Windows system utilities and returned `is_error=False`.
- Ruff, ty, the focused runtime suite, and the direct meta-execute integration check passed.

## Notes

- The first direct import encountered incompatible retired local state, so verification was repeated with a fresh isolated Cadrumo storage root.
