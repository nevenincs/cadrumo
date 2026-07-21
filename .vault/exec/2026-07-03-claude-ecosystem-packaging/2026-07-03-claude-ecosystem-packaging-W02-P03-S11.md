---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a test that the aeat-data wheel packages exactly the corpus binaries under aeat_data with mirrored relative paths and nothing else

## Scope

- `dev/packaging/tests/test_aeat_data_distribution.py`

## Description

- Add `dev/packaging/tests/test_aeat_data_distribution.py` proving the built `aeat-data` companion packages exactly the tracked corpus binaries with mirrored relative paths, and nothing else.
- Assert version parity between the `aeat-data` distribution and the root `aeat` package.
- Add a per-file `ruff` `S603`/`S607` ignore for the subprocess build invocation this test drives.
- Commit `1762e2a483`.

## Outcome

- 3/3 tests passed.

## Notes

No incidents. No skipped work.
