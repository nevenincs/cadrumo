---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S133'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S133 backend service home map

Scope:
- `src/aeat/application`

## Description

- Map each identified CLI business decision to a backend application service destination.
- Keep rendering and schema projection separate from backend policy.

## Outcome

Backend destinations:

- Natural-key work addressing: `src/aeat/application/modelo/_selectors.py` plus a lifecycle command service.
- Create/resume/discard/rename/status/revisions orchestration: new or existing application/modelo work lifecycle service.
- Calculate input bundle assembly and special tax input derivation: `src/aeat/application/modelo/_calculate_input.py` or focused sibling services.
- Verify/file workflow-profile orchestration: application/modelo lifecycle service wrapping `verify_modelo_revision` and `file_modelo_revision`.
- Export default selection and command assembly: `src/aeat/application/modelo/_export.py` or a command wrapper beside it.
- Reconcile command assembly: `src/aeat/application/modelo/_reconcile.py`.
- Project and compare arithmetic: dedicated application/modelo projection/comparison services.
- Text/table rendering only: CLI support module under `src/aeat/entrypoints/cli`.

## Notes

- No code was changed by this mapping step.
