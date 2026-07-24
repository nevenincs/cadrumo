---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S14'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Add the textual dependency (MIT, verified conflict-free) and refresh the lockfile

## Scope

- `pyproject.toml`

## Description

- Add the MIT-licensed textual dependency for the full-screen flow frontend, verified conflict-free against the existing dependency set.
- Refresh the lockfile in the same change.
- Landed in `5bd98452e0`.

## Outcome

Textual is a declared project dependency with a refreshed lockfile, unblocking the full-screen frontend work in this phase. The engine and contract layers stay free of any textual import.

## Notes

None.
