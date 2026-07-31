---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:9a8fc08a9accd8a4e070b1cffe6eeddf3922386c71b2c8f4ace136609a194f98'
step_id: 'S34'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Decide and apply the public-surface disposition for `_build_google_credentials` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.outbound.storage._factory` and consumed cross-package from `src/aeat/entrypoints/cli/_config/_google_sync_calc.py, src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`

## Scope

- `src/aeat/adapters/outbound/storage/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Decide and apply the public-surface disposition for `_build_google_credentials` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.outbound.storage._factory` and consumed cross-package from `src/aeat/entrypoints/cli/_config/_google_sync_calc.py, src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- Tie this row to the registry-plus-tail W01 facade-promotion sweep recorded by the existing `W01.P12.S15` exec record, which split the tail over 13 explicit-pathspec commits.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded per-package ruff checks, direct import smoke tests, targeted package tests, and final clean `pytest --collect-only -q src/aeat` with 14256 collected items. The W01 scaffold pass removed $(W01.P22.S34.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
