---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log

## Scope

- `src/cadrumo/core/logging.py`

## Description

- Add two Settings fields (`cadrumo_log_file_max_bytes`, default 10 MiB; `cadrumo_log_file_backup_count`, default 5) as the diagnostic-log rotation knobs.
- Switch the `cadrumo.log` file handler in `core/logging.py` from `logging.FileHandler` to `logging.handlers.RotatingFileHandler`, wiring `maxBytes`/`backupCount` from the new settings, and import `logging.handlers`.
- Add real-behavior tests: the installed handler is a `RotatingFileHandler` carrying the settings cap/backup count, and writing past the cap rolls over while the retained-backup count stays bounded.
- Add the two fields to the env template and regenerate the env-overrides reference.

## Outcome

The diagnostic log now has a declared rotation lifecycle instead of unbounded growth. `RotatingFileHandler` is a `FileHandler` subclass, so the existing degrade-to-stderr and level-governance tests remain valid. Gates: the rotation suite, the existing logging suite, the settings/env-parity suite, and the env-reference freshness gate all pass (50 passed); ruff clean.

## Notes

Cap and backup count live as central Settings fields per schema-central-config rather than magic literals, since they are deployment knobs. First step of Wave W02 (lifecycle policy); the structural lifecycle gate in S13 will assert this field family maps to the rotation class.
