---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4b17d18c727166596e6e9a2d79fcf4b166303de6962f862ee74e4e6f5cf97e34'
step_id: 'S69'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Align the prerelease selector with the provisionable rolling minor

## Scope

- `dev/ci/python-runtime-matrix.json`

## Changes

- `M` `dev/ci/python-runtime-matrix.json`
- `M` `dev/ci/python_runtime_matrix.py`
- `M` `dev/ci/tests/test_python_runtime_matrix.py`
- `M` `CONTRIBUTING.md`
- `M` `RELEASING.md`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_matrix.py -o addopts='' -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility_workflow.py -o addopts='' -n 0` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/ci/python_runtime_matrix.py dev/ci/tests/test_python_runtime_matrix.py` -> `pass`
- `verify:` `uv lock --check` -> `pass`
- `verify:` `uv python find --offline 3.15` -> `pass`
- `verify:` `uv run --no-sync python -c "from pathlib import Path; from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); assert inventory.next.selector=='3.15'; assert inventory.next.phase.value=='prerelease'; assert inventory.next.blocking is False; assert inventory.next.classifier_eligible is False; contributing=Path('CONTRIBUTING.md').read_text(encoding='utf-8'); assert 'provisionable rolling minor selector' in contributing and '3.15.0b4' in contributing; releasing=Path('RELEASING.md').read_text(encoding='utf-8'); assert 'selector provisionable' in releasing and '3.15.0b4' in releasing; print('selector/docs: pass')"` -> `pass`

## Notes

- Offline provisioning resolves the rolling selector `3.15` to CPython `3.15.0b4`; the former fixed selector `3.15.0-rc.2` has no provisionable interpreter in this environment. The canary remains prerelease, advisory, and unclassified.
