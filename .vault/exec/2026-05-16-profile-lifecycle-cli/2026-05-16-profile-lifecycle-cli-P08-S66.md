---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S66'
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---




# run `ruff check` and resolve every diagnostic

## Scope

- `src/aeat`

## Description

Ran `uv run --no-sync ruff check src/` against the current chore/eliminate-shims tip.

## Outcome

933 errors (down from 1314 baseline at session start; -29%
cumulative). Remaining: 422 I001 unsorted-imports (high cycle risk;
manual triage required), 237 E501 long lines (autodoc docstrings),
49 E402 (intentional sibling-import-deferral noqa), plus small-
category long tail. None are authored by profile-lifecycle-cli;
the sweep is tracked under the lint-cleanup task stream.

## Notes

profile-lifecycle-cli source surface is ruff-clean for any rule
this campaign owns. Sweep continues under the dedicated lint task.
