---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-secure-object-backlog-drain-r2-plan]]'
---



# `secure-object-backlog-drain` `P02.S04`

Removed the two R2-repaired files from the explicit hygiene
classification map.

- Modified: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain-r2/2026-05-22-secure-object-backlog-drain-r2-P02-S04.md`

## Description

Removed `src/aeat/domain/submission/test_repository.py` and
`src/aeat/domain/invoices/test_repository.py` from
`_PENDING_P02_S06_CLASSIFICATIONS` after both files were repaired with
settings-backed explicit secure-object repository injection. The
remaining classified hygiene backlog is now 55 files.

## Tests

`uv run ruff check` passed for the repaired repository tests and the
hygiene guard. A targeted search confirmed the two repaired paths no
longer appear in the classification map.
