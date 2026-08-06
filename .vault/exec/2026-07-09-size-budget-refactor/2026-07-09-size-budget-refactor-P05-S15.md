---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:6f20569bb94bbd369420f99977482a22d9f10f2bd039fb64336b128a57b3864e'
step_id: 'S15'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Record _commands.py, build_server, and _call_tool as deferred to the mcp campaign (peer-hot files under active churn) with no code changes made

## Scope

- `src/aeat/application/wizard/_commands.py`
- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Confirmed via `git log -1` / `git status` that both files sit under the mcp campaign's active development surface, consistent with the plan's ADR (`2026-07-09-size-budget-refactor-adr`) ownership split.
- Applied `full-tree-gate-must-distinguish-owner`: `_server.py:build_server`, `_server.py:_call_tool`, and `_commands.py` are the mcp campaign's, not this campaign's, to fix.
- Made no code changes to either file under this plan.
- Re-ran `test_codebase_size_budgets.py` at campaign close and confirmed the offenders remain present exactly as recorded: `_commands.py` (1339 lines > budget 1305), `build_server` (510 lines > budget 341), and `_call_tool` (209 lines > budget 180, both inside `_server.py`).

## Outcome

One mcp-owned module offender and two mcp-owned callable offenders recorded as deliberately deferred; zero code changes made.

## Notes

No incidents. This Step is a documentation-only tracking action per the plan's design.
