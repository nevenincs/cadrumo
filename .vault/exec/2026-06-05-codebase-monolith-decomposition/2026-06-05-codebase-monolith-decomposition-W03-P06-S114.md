---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S114'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S114 Live Filed-Data Helper Extraction

Scope: `W03.P06.S114` extracts live filed-data selection and listing helpers behind the public live facade.

## Description

- Extract filed-data listing DTOs, declaration selection, and listing-row mapping into `src/aeat/application/live/_filed_data.py`.
- Import and re-export those helpers through `aeat.application.live`.
- Preserve the original register-link based read-surface flags for submitted files, declaration copies, and justificantes.
- Add residual row `S115` for the heavier filed-data capture orchestration that still remains in the live root.

## Outcome

The live package root dropped from 1957 lines to 1894 lines. Ruff reported no findings. The broader live verification gate in S58 reported 110 passing tests and covered filed-data application behavior, focused registry CLI integration, and live filed-data facade imports.

## Notes

This step moves pure selection/listing concerns only. Capture orchestration remains tracked by `S115`.
