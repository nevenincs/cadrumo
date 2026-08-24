---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:de429aa604832e5d50fe47c36cdeff8611e3a76da52f868dbd3ade65c17ca6f1'
step_id: 'S105'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Declare and capture the global --tui root option

## Scope

- `src/cadrumo/entrypoints/cli/_root_command_specs.py`
- `src/cadrumo/entrypoints/cli/_root_cli.py`

## Description

Declare the global root option in the command graph and persist its request in root context.

## Outcome

Every resolved command path now receives the same `aeat --tui` request contract.

## Notes

The dedicated TUI launcher remains unimplemented; routing intentionally refuses.
