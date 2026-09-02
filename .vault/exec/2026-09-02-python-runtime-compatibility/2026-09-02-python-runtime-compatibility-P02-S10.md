---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2ade532e93dea1caef7f5c0c01ffb57daff75406e9a6804ec38c4a8952eb1353'
step_id: 'S10'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add representative-defect tests for the compatibility census

## Scope

- `dev/quality/tests/test_python_compatibility_scan.py`

## Changes

- `A` `dev/quality/tests/test_python_compatibility_scan.py`
- `verify:` `uv run --no-sync pytest -q dev/quality/tests/test_python_compatibility_scan.py -o addopts='' -m 'unit and not external_tool and not os_keychain'; uv run --no-sync ruff check dev/quality/tests/test_python_compatibility_scan.py` -> `pass`
