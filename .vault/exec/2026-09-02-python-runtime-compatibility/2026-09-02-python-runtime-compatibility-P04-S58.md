---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2d2f8c0a1c62d43093e78a8dc8add21c059906d74072fd03f159692b36eadf1e'
step_id: 'S58'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Invoke clean release-cohort construction through its package module

## Scope

- `dev/packaging/release_cohort.py`

## Changes

- `M` `dev/packaging/release_cohort.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/packaging/tests/test_release_cohort.py; uv run --no-sync ruff check dev/packaging/release_cohort.py dev/packaging/tests/test_release_cohort.py; uv run --no-sync python -m dev.packaging.release_cohort --help` -> `pass`
