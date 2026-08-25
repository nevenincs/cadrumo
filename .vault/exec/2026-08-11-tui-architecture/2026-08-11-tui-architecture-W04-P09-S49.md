---
tags: ['#exec', '#tui-architecture']
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1c7c7408f62d0febf5551bbbb0c000968efe847e372795d99b2657b9bb235985'
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

Corrective review pass adds a descendant-focus scroll hook to the owning form
screen. Focused actions now scroll into the one canonical `ContentScroll`
viewport; the overflow assertion remains unchanged and passes deterministically.

Independent review approved S49. The plan step is closed; S50 is the next open
step and no S50 implementation is included in this record.
