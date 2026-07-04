---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S24'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Emit the plugin skills/ tree (SKILL.md plus reference material) from the single authored harness source

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to emit the plugin `skills/` tree from the single authored harness source, one directory per skill carrying `SKILL.md` plus reference material.
- Emit 34 skills, matching the authored harness source count.
- Commit `444e33f64b`.

## Outcome

- The materialiser emits the full skills tree for the plugin layout target with no duplicated authoring source.

## Notes

No incidents. No skipped work.
