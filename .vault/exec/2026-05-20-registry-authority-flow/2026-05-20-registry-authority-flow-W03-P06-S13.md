---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S13'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W03.P06.S13`

Migrated Google config registry loading to authority snapshots.

- Modified: `_google.py`
- Created: this execution record

## Description

Replaced raw loader plus local snapshot construction with `ValidatedRegistryAuthority.load(...).snapshot(...)` while preserving unknown-modelo error reporting.

## Tests

`uv run pytest src/aeat/entrypoints/cli/_config/test_google_sync_calc_pull_flag.py -q` passed.
