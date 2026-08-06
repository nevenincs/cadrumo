---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-07-17'
body_hash: 'sha256:afa2f74be8c1d8560ec011d4148261f8fb8d97aab3f9df54ce8c9defe0060a7d'
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
