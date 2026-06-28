---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S138'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S138 backend homes for business and render helpers

Scope:
- `src/aeat/application`

## Description

- Separate backend business homes from render-only helper homes.

## Outcome

Backend business homes:

- `src/aeat/application/modelo/_selectors.py` for target and revision selection policy.
- `src/aeat/application/modelo/_actions.py` and a focused lifecycle wrapper for work create/calculate/verify/file/import/amend orchestration.
- `src/aeat/application/modelo/_calculate_input.py` for calculation input bundle construction.
- `src/aeat/application/modelo/_export.py` for exportable revision and export command policy.
- `src/aeat/application/modelo/_reconcile.py` for reconciliation command policy.
- `src/aeat/application/modelo/_taxation_comparison.py` for taxation comparison.
- A dedicated projection service for Modelo 130 to Modelo 100 projection and year comparison.

Render-only CLI homes:

- A bounded modelo CLI rendering helper module for work-unit, revision, verification, filing, and export lines.
- `_modelo_payloads.py` for schemas only.
- `_modelo_work.py` for Typer work-app construction only.

## Notes

- Render helpers must not import domain internals for calculation, registry, workflow, or persistence decisions.
