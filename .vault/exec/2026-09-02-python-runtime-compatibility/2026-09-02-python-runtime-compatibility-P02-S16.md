---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c7388b0ad238c6be31c5ef4d8b7c1b482cb77db3bff32ba3f41967390389ba6d'
step_id: 'S16'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Enforce annotations as the sole project future directive

## Scope

- `dev/tests/test_import_hygiene_scan.py`

## Changes

- `M` `dev/tests/test_import_hygiene_scan.py`
- `verify:` `uv run --no-sync ruff format --check dev/tests/test_import_hygiene_scan.py; uv run --no-sync ruff check dev/tests/test_import_hygiene_scan.py; uv run --no-sync python -m py_compile dev/tests/test_import_hygiene_scan.py; uv run --no-sync pytest -q dev/tests/test_import_hygiene_scan.py -o addopts='' -m 'unit and hex_core' -k 'future_directive' -n 0` -> `pass`
