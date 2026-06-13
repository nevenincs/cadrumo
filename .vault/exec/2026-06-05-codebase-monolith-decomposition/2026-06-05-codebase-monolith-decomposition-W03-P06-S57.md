---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S57'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S57 Live Root Model Extraction

Scope: `W03.P06.S57` decomposes the application live package root while preserving public live facade imports.

## Description

- Extract filed-data and IVA remote-state report DTOs and enums into `src/aeat/application/live/_remote_state_models.py`.
- Import and re-export the extracted DTOs from `src/aeat/application/live/__init__.py` so consumers continue to use `aeat.application.live`.
- Preserve the secure acquisition manifest repository in the root for this slice because it still binds storage namespaces and active-bucket resolution.
- Add residual plan rows for the remaining live root service extractions: IVA remote-state services and filed-data capture/listing services.

## Outcome

The live package root dropped from 2605 lines to 2252 lines, and the extracted model module is 412 lines. Application and CLI live-read tests covering the moved model surface passed.

## Notes

This step intentionally does not claim the live root is below the final module-size target. Residual rows `S113` and `S114` now track the remaining service-family extractions needed before the hard size guard can pass.
