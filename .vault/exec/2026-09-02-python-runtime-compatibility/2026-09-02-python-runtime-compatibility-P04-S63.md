---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6c48b18c380fb8a73e1405672683787431dbd02669452d8cbb220ad9a2e78784'
step_id: 'S63'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Prove clean cohort construction accepts digest-bound local wheels

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Changes

- `M` `dev/packaging/tests/test_release_cohort.py`
- `verify:` `uv run --no-sync pytest -q -p no:randomly dev/packaging/tests/test_release_cohort.py dev/packaging/tests/test_python_cohort_digest_assertions.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/packaging/python_cohort.py dev/packaging/tests/test_release_cohort.py` -> `pass`
