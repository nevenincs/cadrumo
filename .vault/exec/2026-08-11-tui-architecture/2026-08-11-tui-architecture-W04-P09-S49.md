---
tags: ['#exec', '#tui-architecture']
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
step_id: 'S49'
related: ["[[2026-08-11-tui-architecture-plan]]"]
---

# Relocate immutable form presentation contracts and widgets

## Scope

- `src/cadrumo/entrypoints/tui/components/forms.py`
- direct form-contract consumers

## Description

Move immutable form field/page contracts and choice helpers to the canonical
forms component module, with no orchestration, backend validation, or state.

## Outcome

Form contracts and helpers have one canonical owner; consumers import directly
from `components.forms`, and the legacy inbound facade no longer republishes
them. Ruff passes and the focused form lane passes (10 tests).

## Notes

S49 remains open pending independent review.
