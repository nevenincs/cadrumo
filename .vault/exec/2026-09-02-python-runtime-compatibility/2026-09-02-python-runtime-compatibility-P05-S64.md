---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f1a61564d9aeb374ccdf75d8f64de55b6723eae39a800bfc8f4770875f46bb89'
step_id: 'S64'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Promote 3.14 classifier eligibility after source binary and artifact evidence

## Scope

- `dev/ci/python-runtime-matrix.json`

## Changes

- `M` `dev/ci/python-runtime-matrix.json`
- `M` `dev/ci/tests/test_python_runtime_matrix.py`
- `M` `dev/packaging/tests/test_classifier_parity.py`
- `M` `pyproject.toml`
- `M` `packaging/cadrumo_data_manuals/pyproject.toml`
- `M` `packaging/cadrumo_data_official/pyproject.toml`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_classifier_parity.py dev/ci/tests/test_python_runtime_matrix.py -o addopts='' -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility_workflow.py -o addopts='' -n 0` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/packaging/tests/test_classifier_parity.py dev/ci/tests/test_python_runtime_matrix.py` -> `pass`
- `verify:` `uv lock --check` -> `pass`
- `verify:` `uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); assert [r['minor'] for r in inv['stable'] if r['classifier_eligible']]==['3.13','3.14']; assert inv['next']['minor']=='3.15' and inv['next']['phase']=='prerelease' and inv['next']['blocking'] is False and inv['next']['classifier_eligible'] is False; paths=['pyproject.toml','packaging/cadrumo_data_manuals/pyproject.toml','packaging/cadrumo_data_official/pyproject.toml']; expected={'3.13','3.14'}; assert all({c.rsplit(' :: ',1)[-1] for c in tomllib.load(open(path,'rb'))['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}==expected for path in paths)"` -> `pass`

## Notes

- Sealed cohort construction and artifact verification passed at source commit `10154f14aefd237ea7163940fb6bcfc1e96b95f3`; source and binary probes passed on CPython `3.14.6`.
- CPython `3.15.0b4` remains prerelease and advisory: source compatibility passed, while binary evidence reports the attributable upstream PyYAML `missing-wheel` result. It remains unclassified.
