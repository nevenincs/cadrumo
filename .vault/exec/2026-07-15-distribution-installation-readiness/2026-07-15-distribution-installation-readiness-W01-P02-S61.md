---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S61'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Make MCP identity reads unlock profiles created by sibling CLI subprocesses

## Scope

- `src/cadrumo`

## Description

- Promote the cold-session health assessment through the workflow public facade.
- Retry only the canonical missing-session failure under the configured master-key provider.
- Preserve pointer-source and repair semantics after the scoped session closes.
- Route MCP `whoami` through the session-aware projection and add a real durable-profile regression.

## Outcome

- A long-running process now reads a profile created by a sibling CLI process without reporting it as unreadable.
- The regression persists a real encrypted profile, closes its original session, reopens it through production custody, and confirms the session is closed again afterward.
- Ruff, ty, 29 focused workflow/MCP tests, and a direct cross-process source proof passed.

## Notes

- This step was inserted after the first installed MCP oracle run exposed the missing-session defect. S07 was re-opened until a wheel containing this committed fix is rebuilt and retested.
