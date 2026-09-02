---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5547db338652fd1b58b264d2b880dfdef8c686448ac8de4217b236861c2d76bc'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# `python-runtime-compatibility` `P01` summary

## Changes

- `M` `pyproject.toml`
- `M` `uv.lock`
- `A` `dev/ci/python-runtime-matrix.json`
- `A` `dev/ci/python_runtime_matrix.py`
- `A` `dev/ci/tests/test_python_runtime_matrix.py`
- `M` `dev/audit/security.py`
- `M` `dev/audit/tests/test_security.py`
- `M` `dev/packaging/tests/test_release_cohort.py`
- `verify:` `uv lock --check; uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_matrix.py dev/audit/tests/test_security.py dev/packaging/tests/test_release_cohort.py; uv run --no-sync ruff check dev/ci/python_runtime_matrix.py dev/ci/tests/test_python_runtime_matrix.py dev/audit/security.py dev/audit/tests/test_security.py dev/packaging/tests/test_release_cohort.py; uv run --no-sync python -m dev.ci.python_runtime_matrix; vaultspec-core vault check all --feature python-runtime-compatibility --limit 200` -> `pass`
