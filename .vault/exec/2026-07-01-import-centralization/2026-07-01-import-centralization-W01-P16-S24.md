---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Decide and apply the public-surface disposition for `_refuse_duplicate_label` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.user_profile._orchestration` and consumed cross-package from `src/aeat/application/wizard/_commands.py`

## Scope

- `src/aeat/application/user_profile/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Decide and apply the public-surface disposition for `_refuse_duplicate_label` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.user_profile._orchestration` and consumed cross-package from `src/aeat/application/wizard/_commands.py`.
- Tie this row to the registry-plus-tail W01 facade-promotion sweep recorded by the existing `W01.P12.S15` exec record, which split the tail over 13 explicit-pathspec commits.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded per-package ruff checks, direct import smoke tests, targeted package tests, and final clean `pytest --collect-only -q src/aeat` with 14256 collected items. The W01 scaffold pass removed $(W01.P16.S24.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
