---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9f1d5e0b03488f49e4c9533c44428a2225372b33ca654925374da694da699fdf'
step_id: 'S71'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Build and validate runtime-specific sealed wheelhouses for every blocking CPython minor

## Scope

- `dev/packaging/runtime_wheelhouse.py`
- `dev/packaging/python_cohort.py`
- `dev/ci/python_runtime_compatibility.py`

## Changes

- `M` `dev/ci/python_runtime_compatibility.py`
- `M` `dev/ci/tests/test_python_runtime_compatibility.py`
- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/runtime_wheelhouse.py`
- `M` `dev/packaging/tests/_cohort_attestation.py`
- `M` `dev/packaging/tests/test_acquire_tooling.py`
- `A` `dev/packaging/tests/test_runtime_wheelhouse.py`
- `M` `dev/packaging/tests/test_python_cohort_digest_assertions.py`
- `M` `src/cadrumo_harness/_workspace.py`
- `M` `src/cadrumo_harness/tests/_plugin_cohort.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py dev/packaging/tests/test_runtime_wheelhouse.py -o addopts=''` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py -k advisory_missing_wheels -o addopts=''` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py dev/packaging/tests/test_python_cohort.py src/cadrumo_harness/tests/test_plugin_workspace.py -o addopts=''` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/ci/python_runtime_compatibility.py dev/packaging/runtime_wheelhouse.py dev/packaging/python_cohort.py dev/packaging/tests/test_runtime_wheelhouse.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.packaging.release_cohort verify --cohort-dir var/python-runtime-wheelhouse-snapshot-0c9e915444e8/var/release-cohort-python-313-314-sealed` -> `pass`
- `verify:` `binary probes CPython 3.13.14 and 3.14.6, offline/no-index/find-links/require-hashes` -> `pass`
- `verify:` `same-commit matrix at ea2f347ba22a5d566f18f8c97a995c22348eb3d9 with cohort d57b1de3c709...: source CPython 3.13.14, 3.14.6, 3.15.0b4; sealed offline binary CPython 3.13.14 and 3.14.6; advisory 3.15 missing-wheel pydantic-core/PyYAML` -> `pass`
