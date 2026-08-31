---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:fb80bd937852994ef7b2bc26f46a043706069741ae67c6dbf597e7d81a792374'
step_id: 'S139'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
## Changes

- `M` `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `A` `src/cadrumo/application/calculations/_cross_period_external_evidence.py`
- `M` `src/cadrumo/application/calculations/__init__.py`

## Notes

Verification evidence required by P05.S139:

```text
vaultspec-rag search 'cross period clean state calculation dependency diagnostics' --type code
Refusing to search against the running service.
This vaultspec-rag client is 0.4.2 but the running service is 0.4.10.
exit 1

uv run --no-sync ruff check src/cadrumo/application/calculations/cross_period_clean_state.py src/cadrumo/application/calculations/_cross_period_external_evidence.py src/cadrumo/application/calculations/__init__.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/calculations/cross_period_clean_state.py src/cadrumo/application/calculations/_cross_period_external_evidence.py src/cadrumo/application/calculations/__init__.py
3 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/calculations/tests/test_cross_period_external_evidence.py src/cadrumo/application/calculations/tests/test_cross_period_clean_state_provenance.py src/cadrumo/application/calculations/tests/test_unresolved_identity_is_not_a_mismatch.py
31 tests collected in 3.93s
exit 0
deselected 0

uv run --no-sync pytest -n 0 src/cadrumo/application/calculations/tests/test_cross_period_external_evidence.py src/cadrumo/application/calculations/tests/test_cross_period_clean_state_provenance.py src/cadrumo/application/calculations/tests/test_unresolved_identity_is_not_a_mismatch.py
11 failed, 20 passed in 227.54s (0:03:47)
ProfileCustodyRefusedError: KDF_SUPERVISION_UNAVAILABLE
EOFError: profile KDF worker closed its pipe
exit 1

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); targets=('src/cadrumo/application/calculations/cross_period_clean_state.py','src/cadrumo/application/calculations/_cross_period_external_evidence.py'); print('POLICY='+str(MODULE_POLICY.default_limit)); [print(path+'='+str(measures[path])) for path in targets]"
POLICY=1250
src/cadrumo/application/calculations/cross_period_clean_state.py=1128
src/cadrumo/application/calculations/_cross_period_external_evidence.py=130
exit 0
```

The runner's 11 failures begin in profile-capsule creation before the extracted evidence code runs, via the shared custody KDF worker (`KDF_SUPERVISION_UNAVAILABLE`); no external owner was changed or retried.

## Repair verification

```text
uv run --no-sync ruff check src/cadrumo/application/calculations/cross_period_clean_state.py src/cadrumo/application/calculations/_cross_period_external_evidence.py src/cadrumo/application/calculations/__init__.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/calculations/cross_period_clean_state.py src/cadrumo/application/calculations/_cross_period_external_evidence.py src/cadrumo/application/calculations/__init__.py
3 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/calculations/tests/test_unresolved_identity_is_not_a_mismatch.py
5 tests collected in 3.04s
exit 0
deselected 0

uv run --no-sync pytest -n 0 src/cadrumo/application/calculations/tests/test_unresolved_identity_is_not_a_mismatch.py
============================== 5 passed in 9.63s ==============================
exit 0

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); print('POLICY='+str(MODULE_POLICY.default_limit)); print('src/cadrumo/application/calculations/cross_period_clean_state.py='+str(measures['src/cadrumo/application/calculations/cross_period_clean_state.py'])); print('src/cadrumo/application/calculations/_cross_period_external_evidence.py='+str(measures['src/cadrumo/application/calculations/_cross_period_external_evidence.py']))"
POLICY=1250
src/cadrumo/application/calculations/cross_period_clean_state.py=1127
src/cadrumo/application/calculations/_cross_period_external_evidence.py=130
exit 0
```
