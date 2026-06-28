---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S129'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S129 modelo addressing surface risk inventory

Scope:
- `src/aeat/entrypoints/cli`

## Description

- Inventory the modelo-addressing production files discovered by `fd`.
- Classify each as command registration, payload schema, helper, or test/support surface.

## Outcome

Modelo-addressing production surfaces:

- `src/aeat/entrypoints/cli/_modelo.py`: monolithic command implementation and primary extraction target.
- `src/aeat/entrypoints/cli/_modelo_payloads.py`: typed output schemas; allowed to keep IDs and typed fields but should not encode policy.
- `src/aeat/entrypoints/cli/_modelo_work.py`: work app Typer construction; should remain registration-only.
- `src/aeat/application/modelo/_selectors.py`: backend selector boundary; policy belongs here or in neighboring application services, not in CLI helpers.
- `src/aeat/application/modelo/_export.py`, `_reconcile.py`, `_history.py`, `_taxation_comparison.py`, `_result_summary.py`, and `_revision_persistence.py`: backend service homes for extracted behavior.

## Notes

- No code was changed by this inventory step.
