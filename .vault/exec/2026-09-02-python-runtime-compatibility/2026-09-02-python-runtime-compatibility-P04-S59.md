---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:02ea191b478aeb4c912b8f568525bb986614f64aa397f434c6e6bedb8bf4d812'
step_id: 'S59'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Prove clean release-cohort subprocess imports remain package-correct

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Changes

- `M` `dev/packaging/tests/test_release_cohort.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/packaging/tests/test_release_cohort.py; uv run --no-sync ruff check dev/packaging/tests/test_release_cohort.py` -> `pass`

## Notes

- `uv run --no-sync python -m dev.packaging.release_cohort build --output var/release-cohort-package-module-proof-20260902` -> `fail` after the clean child imported and executed `dev.packaging.release_cohort`; the existing `uv --require-hashes` local-wheel install refused `cadrumo-0.2.2-py3-none-any.whl` because it had no hash, and staging was removed.
