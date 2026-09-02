---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b7705d56c1b04a6e4ae2e423228d2be63e4f8d861ffc90c3b8ecefda4523b4de'
step_id: 'S34'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Enforce root and companion classifier parity and prerelease exclusion

## Scope

- `dev/packaging/tests/test_classifier_parity.py`

## Changes

- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_classifier_parity.py -o addopts='' -n 0; uv run --no-sync ruff check dev/packaging/tests/test_classifier_parity.py` -> `pass`
