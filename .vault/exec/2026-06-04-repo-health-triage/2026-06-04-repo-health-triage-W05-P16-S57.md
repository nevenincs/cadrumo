---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
step_id: 'S57'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S57 - filing-status token relocation blocked by overview WIP

Scope: Wave `W05`; Phase `W05.P16`; Step `S57`.

## Description

- Inspected `src/aeat/application/operator_surface/_filing_status_token.py` and confirmed it is a token-only shim for the LIVE `filed` command name.
- Confirmed importing `aeat.application.overview._status` directly is not safe for the operator-surface contract because Python loads the heavy `overview` package initializer before the submodule.
- Identified the proper no-shim resolution: relocate the `FilingStatus` enum to a lightweight operator-surface/application authority module, update the operator-surface contract and overview export to that canonical site, and delete the token-only shim in the same atomic commit.

## Blocker

`src/aeat/application/overview/__init__.py` already has unrelated calendar-event WIP in the shared worktree. The architecture-boundaries rule requires a symbol relocation to land atomically across the canonical site and every consumer, but the required overview consumer/export file is currently owned by that unrelated WIP. S57 therefore remains open and must not be checked in the plan until the overview WIP is either committed or otherwise cleared by its owner.

## Verification

- `git diff -- src/aeat/application/overview/__init__.py`
- `fd "filing_status_token|_filing_status_token" src/aeat -t f`
- `rg -n "from \\.{0,2}overview import FilingStatus|from .*overview._status import FilingStatus|FilingStatus" src/aeat/application/operator_surface src/aeat/entrypoints src/aeat/application -g "*.py"`
