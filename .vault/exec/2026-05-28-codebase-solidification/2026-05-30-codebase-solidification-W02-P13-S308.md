---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S308'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S308`

Replaced `logging.getLogger` with `get_logger` from `aeat.core.logging` in the Google Drive live test module.

- Modified: `src/aeat/adapters/outbound/storage/test_google_drive_live.py`

## Description

Removed `import logging` and added `from aeat.core.logging import get_logger`. Changed `_log = logging.getLogger(__name__)` to `_log = get_logger(__name__)`. Import uses the absolute form consistent with how `aeat.adapters.outbound.storage._local` imports `get_logger`.

## Tests

File parses cleanly. Live-gated; not exercised in the default suite.
