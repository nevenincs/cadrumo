---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:b13c07224ce27ff66c959b9b16b36c8739c17eea50e83eeb084d74ae2e753ab1'
step_id: S577
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S577`

Added `ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY` markers on `_drive_service` and `_sheets_service` in `adapters/outbound/google/_calc_sheets_apply.py`.

- Modified: `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`

## Description

Both functions call `googleapiclient.discovery.build()` which returns an untyped `Resource` object; no stub in the ecosystem narrows the concrete type. The rationale markers document this third-party boundary escape at the def line.

## Tests

W10 inventory test asserts both factory functions carry the marker. 27/27 passed.
