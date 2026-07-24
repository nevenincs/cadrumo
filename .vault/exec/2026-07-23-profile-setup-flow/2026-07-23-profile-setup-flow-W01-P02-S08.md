---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S08'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Extend the Translatable-prefix validator into a reference-only copy gate that rejects literal copy strings at flow construction

## Scope

- `src/cadrumo/application/wizard/_models.py`

## Description

- Verify the reference-only copy discipline against the landed substrate
  contract instead of authoring a redundant gate.
- `FlowPage.prompt` / `help` (and every copy slot on the FlowDefinition
  family) are typed `CopyRef` fields under strict pydantic config: a
  literal prose string cannot occupy a copy slot structurally.
- The copy assembler refuses an unresolved reference loudly at render
  (live-verified by the substrate stream), so prose smuggled AS a ref
  string fails the first time it renders, never silently displays.
- The wizard catalogue side keeps its existing enforcement: the
  `WizardFlow` Translatable-prefix validator rejects any copy key
  outside the flow's namespace at construction.

## Outcome

No new code: the Step's intent (reject literal copy at construction) is
satisfied by the substrate's typed CopyRef structure plus the existing
wizard prefix validator, with render-time loud refusal as
defence-in-depth. Closing on verification rather than duplicate
implementation per the no-parallel-authority discipline.

## Notes

If a future substrate change loosens a copy slot to a bare string, the
strict-config pydantic models make that a visible contract change, not
a silent drift.
