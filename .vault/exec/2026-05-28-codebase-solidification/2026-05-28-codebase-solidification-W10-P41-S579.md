---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S579
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S579`

Extended `test_w09_p38_rationale_inventory.py` to include `_borrador_100.py` in the S559 mandate list.

- Modified: `src/aeat/test_w09_p38_rationale_inventory.py`

## Description

The `_S559_MANDATE` list previously contained four snapshot-dispatch files (`_censo.py`, `_expedientes.py`, `_notifications.py`, `_snapshot_base.py`). Added `_borrador_100.py` as the fifth entry. This is why the S578 marker-token error escaped detection in W09: the file was not covered by the parametrized test.

## Tests

The extended parametrized test now covers 5 files. `_borrador_100.py-_derive_snapshot_id` passes with the corrected `KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH` token. 27/27 passed.
