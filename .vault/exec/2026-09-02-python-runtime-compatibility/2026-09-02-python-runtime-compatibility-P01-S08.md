---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9e4b7ef0a36b0ce6f46dd4fd61c8de6081cc7fc4bb4757e80c2e6fea765fe256'
step_id: 'S08'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Guard the exact CPython release-builder identity

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Changes

- `M` `dev/packaging/tests/test_release_cohort.py`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_release_cohort.py; uv run --no-sync ruff check dev/packaging/tests/test_release_cohort.py` -> `pass`
