---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:71c827d57406348daadd5d06222c3abc324cef68285c449f9342a6352df4173a'
step_id: 'S15'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Compile every dev and src module against the oldest supported grammar

## Scope

- `dev/tests/test_every_source_file_parses.py`

## Changes

- `M` `dev/tests/test_every_source_file_parses.py`
- `verify:` `uv run --no-sync ruff format --check dev/tests/test_every_source_file_parses.py; uv run --no-sync ruff check dev/tests/test_every_source_file_parses.py; uv run --no-sync python -m py_compile dev/tests/test_every_source_file_parses.py; uv run --no-sync pytest -q dev/tests/test_every_source_file_parses.py -o addopts='' -m 'unit and hex_core' -n 0` -> `pass`
