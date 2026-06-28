---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S124'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S124` External CLI abstraction coverage

Step scope: `src/aeat/entrypoints/cli`.

## Description

- Verified modelo command handlers for work lifecycle, export, reconcile, history, compare, and projection.
- Verified payload schema compatibility and structured ID retention.
- Verified natural-key common-path coverage and legacy raw-ID compatibility.

## Outcome

External CLI coverage passed:

- `.venv\Scripts\python.exe -m pytest -q src/aeat/entrypoints/cli/test_modelo_work_ux.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py src/aeat/entrypoints/cli/test_modelo_export_verb.py`
  passed `35` tests.
- `.venv\Scripts\python.exe -m pytest -q src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py src/aeat/entrypoints/cli/test_modelo_history_verb.py src/aeat/entrypoints/cli/test_modelo_compare.py`
  passed `16` tests.
- `.venv\Scripts\python.exe -m pytest -q src/aeat/entrypoints/cli/test_modelo_payloads.py src/aeat/entrypoints/cli/test_modelo_projection.py`
  passed `12` tests.

Ruff passed for the CLI slice:

- `.venv\Scripts\ruff.exe check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_payloads.py src/aeat/entrypoints/cli/_modelo_work.py`

## Notes

Exact IDs remain in structured output and explicit exact-addressing parameters by
design; the common command path is covered through modelo/year/period addressing
and command-specific revision defaults.
