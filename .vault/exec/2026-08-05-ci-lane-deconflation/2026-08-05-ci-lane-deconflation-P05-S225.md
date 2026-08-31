---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5a0d9418f694df1bd40b04b5ad69b0e85daad06f72d21ede760a88605e02125e'
step_id: 'S225'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S225`

## Scope

- `P05.S225`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- `A` `src/cadrumo/entrypoints/cli/tests/_machine_secret_channels_support.py`
- `A` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess_refusals.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S225.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/entrypoints/cli/tests/_machine_secret_channels_support.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess_refusals.py` emitted `All checks passed!` (exit 0); `uv run --no-sync ruff format --check src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/entrypoints/cli/tests/_machine_secret_channels_support.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess_refusals.py` emitted `3 files already formatted` (exit 0); `git diff --check` exited 0.
- `uv run --no-sync pytest -o addopts='' --collect-only -q -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess_refusals.py` collected 70 tests (exit 0); `uv run --no-sync pytest -o addopts='' -n 0 -q -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess_refusals.py` emitted `70 passed in 487.26s` (exit 0).
- `uv run --no-sync python -c "from dev.audit.size_budget import measure_module_lines; actual = measure_module_lines(); key = 'src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py'; print(f'{key}: {actual[key]} lines; default module budget 1250; exit 0')"` emitted `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py: 654 lines; default module budget 1250; exit 0`; no policy or baseline changed.
- Before S225 plan mutation, `HEAD` was `61b8021325565c76258a557c289d3a12deb10c0a`, the default index plan blob was `dafa57578eb05350b52c0aac54923edec1427506`, and the peer worktree plan blob was `79f023bf96828dd16a52d2e0e08c646a5c24a70b`; the isolated commit stages only the S225 row and generated body hash while preserving the peer plan hunks byte-identically.
