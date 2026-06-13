---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P01.S01 - current modelo CLI root inventory

Scope: inventory the current modelo CLI root size, command groups, helper groups, and private backend touchpoints.

## Description

- Count current legacy root size in `src/aeat/entrypoints/cli/_modelo.py`.
- Discover existing extracted modelo CLI modules with `fd`.
- Inventory Typer command groups and command decorators in the legacy root with `rg`.
- Inventory private backend touchpoints and registry authority access in the legacy root with `rg`.
- Locate existing architecture and size guard tests for the decomposition baseline.

## Outcome

The legacy root remains a monolith at 4248 lines. It registers top-level modelo commands, `bindings`, `work`, `filing-record`, `verification-report`, and `audit` subgroups, with work lifecycle, calculation, revision, verification, filing, amendment, reconciliation, and history command bodies still inside the same file.

Existing extracted sibling modules are present for CLI support, export, IVA wallet, M036, maritime, payloads, projection, rendering, work app creation, and workflow-run commands. The root still directly imports private domain internals such as calculation revisions, row models, and work units, and directly constructs registry query services through `resources().modelos.authority`.

The existing static guards freeze extracted modules and hold `_modelo.py` under broad legacy size budgets, but the guard scope does not yet freeze the root private-import or registry-authority debt itself.

## Notes

This baseline supports W01.P02 guardrail work. No code files were changed by this inventory step.
