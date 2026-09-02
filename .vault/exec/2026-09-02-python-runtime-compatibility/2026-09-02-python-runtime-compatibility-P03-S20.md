---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8aa3bae1d1ba42189a161bc2dffd9892cc6648c16cd8fccf3b0c5b4c0712e85e'
step_id: 'S20'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Test source versus binary evidence and foreign cohort refusal

## Scope

- `dev/packaging/tests/test_evidence.py`

## Changes

- `M` `dev/packaging/tests/test_evidence.py`
- `verify:` `uv run --no-sync ruff check dev/packaging/tests/test_evidence.py; uv run --no-sync python -m py_compile dev/packaging/tests/test_evidence.py; uv run --no-sync pytest -q dev/packaging/tests/test_evidence.py -k 'source_and_binary or missing_wheel or foreign_cohort' -o addopts=''` -> `pass`
