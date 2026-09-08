---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:ef48d7ded30323614b2aab08e1afca5644db032939be6655f6c33b6aa1998dfe'
step_id: 'S225'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Make the reachability audit derive every shipped python -m surface from either __main__.py or an exact top-level __name__ == '__main__' guard, with negative controls for prose and nested comparisons; thereby recognize the accepted Windows inherited-HANDLE bootstrap as a product root and retain its security-critical subprocess matrix instead of classifying or deleting it as orphaned.

## Scope

- `Reachability module-root discovery and detector-teeth tests`
- `Windows machine-secret bootstrap and subprocess matrix`
- `accepted machine-secret channel decision`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `dev/audit/unreachable_code.py`
- `M` `dev/audit/tests/test_unreachable_code.py`
- `M` `src/cadrumo/entrypoints/cli/_windows_profile_secret_bootstrap.py`
- `M` `src/cadrumo/entrypoints/cli/tests/_machine_secret_channels_support.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S225.md`
- `verify:` `uv run --no-sync ruff check dev/audit/unreachable_code.py dev/audit/tests/test_unreachable_code.py src/cadrumo/entrypoints/cli/_windows_profile_secret_bootstrap.py src/cadrumo/entrypoints/cli/tests/_machine_secret_channels_support.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s225 dev/audit/tests/test_unreachable_code.py` -> `pass (51 passed)`
- `verify:` `uv run --no-sync pytest -q -n 0 -m integration --basetemp .tmp/pytest-s225-integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py -k 'platform_descriptor_bootstrap or platform_recovery_descriptors'` -> `pass (2 passed, 16 deselected)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 60 unreachable modules, 306 exact unused symbols, 8 orphaned tests, 2029/2090 shipped modules reachable; five derived roots plus workspace sibling)`

- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s225-fast dev/audit/tests/test_unreachable_code.py -k 'module_execution_surface or repository_discovers_its_module_execution_roots'` -> `pass (2 passed, 49 deselected after text-prefilter refinement)`
