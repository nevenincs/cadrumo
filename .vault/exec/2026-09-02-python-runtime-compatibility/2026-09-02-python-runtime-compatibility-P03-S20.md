---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a6428999b9133fd4fb27e0637cee12a5ff46f9ca122d31afba946e75a3919764'
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
