---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S61'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S61 Workflow Engine Helper Extraction

Scope: `W03.P06.S61` decomposes workflow engine helper behavior behind the public workflow facade.

## Description

- Extract workflow unhandled-exception and site-health recording helpers into `src/aeat/application/workflow/_engine_recording.py`.
- Extract deadline metadata enums plus period, certificate-expiry, enum, and summary helpers into `src/aeat/application/workflow/_engine_helpers.py`.
- Keep `WorkflowEngine` as the orchestrator and delegate failure recording through private helper functions.
- Preserve existing stage call sites and run-id calculation semantics by passing the engine's current-run callback to the recording helper.
- Preserve distinct translated error paths for generic period mapping and filing-year-only resolution.

## Outcome

`src/aeat/application/workflow/_engine.py` is now 1,149 lines, `src/aeat/application/workflow/_engine_recording.py` is 101 lines, and `src/aeat/application/workflow/_engine_helpers.py` is 92 lines. Public consumers continue to import through `aeat.application.workflow`.

## Notes

This remains helper-level decomposition. Larger stage extraction would carry more behavioral risk and should stay in later workflow rows.
