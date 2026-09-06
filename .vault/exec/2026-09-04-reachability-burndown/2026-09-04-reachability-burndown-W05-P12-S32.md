---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:d163d4e3eb4704fe23fc39139089967f7fcf99e9437d443494f804d896b1647f'
step_id: 'S32'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Refuse a workspace door wired in part: the Ledger launcher passed classify_action while never passing classification_target or classification_submitter, and no production implementation of LedgerClassificationSubmitterV1 exists, so the classification door was refused at runtime while the call site read as configured; correct the launcher and derive each area's required injection group from the controller's own guard

## Scope

- `dev/quality/tests/test_workspace_doors_are_wholly_wired.py`

## Changes

- `A` `dev/quality/tests/test_workspace_doors_are_wholly_wired.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests src/cadrumo/entrypoints/tui -q` -> `pass`
