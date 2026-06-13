---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S53'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S53 - decompose application modelo action helpers

Scope: `src/aeat/application/modelo/_actions.py`, `src/aeat/application/modelo/_workflow_gate.py`, `src/aeat/application/modelo/_m210_rate.py`.

## Description

- Extract revision workflow period resolution and workflow-engine adapter objects into `src/aeat/application/modelo/_workflow_gate.py`.
- Extract Modelo 210 rate resolution into `src/aeat/application/modelo/_m210_rate.py`.
- Preserve `aeat.application.modelo` public facade exports for workflow period resolution and modelo action services.
- Preserve legacy `_actions.py` private compatibility imports for `_RevisionInputsProvider` and `WorkflowInputMismatchError` while moving implementation ownership out of the monolith.
- Keep `_actions.py` as the lifecycle orchestrator that calls the extracted workflow-gate builder instead of owning filing adapter construction directly.

## Outcome

`src/aeat/application/modelo/_actions.py` shrank substantially, and workflow-gate adapter logic plus Modelo 210 rate resolution now live in focused application modules. Public facade imports remain stable.

## Notes

No CLI behavior was changed. No raw-id addressing behavior was changed. The extraction intentionally leaves facade imports stable and avoids adding consumer imports to the new private modules.
