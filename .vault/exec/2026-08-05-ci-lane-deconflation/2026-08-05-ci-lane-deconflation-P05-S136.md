---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:60081d600a0763c6272366b4486295fd77c610984c0e3115f48865e616d26f66'
step_id: 'S136'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
## Changes

- `M` `src/cadrumo/application/auth/operator.py`
- `A` `src/cadrumo/application/auth/operator_result_projections.py`

## Notes

Verification evidence required by P05.S136:

```text
uv run --no-sync ruff check src/cadrumo/application/auth/operator.py src/cadrumo/application/auth/operator_result_projections.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/auth/operator.py src/cadrumo/application/auth/operator_result_projections.py
2 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/auth/tests/test_operator.py src/cadrumo/application/auth/tests/test_operator_probe_credential_resolution.py src/cadrumo/entrypoints/cli/tests/test_auth_configure_identity_projection.py
46 tests collected in 3.90s
exit 0
deselected 0

uv run --no-sync pytest -n 0 src/cadrumo/application/auth/tests/test_operator.py src/cadrumo/application/auth/tests/test_operator_probe_credential_resolution.py src/cadrumo/entrypoints/cli/tests/test_auth_configure_identity_projection.py
======================== 46 passed in 82.12s (0:01:22) ========================
exit 0

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); targets=('src/cadrumo/application/auth/operator.py','src/cadrumo/application/auth/operator_result_projections.py'); print('POLICY='+str(MODULE_POLICY.default_limit)); [print(path+'='+str(measures[path])) for path in targets]"
POLICY=1250
src/cadrumo/application/auth/operator.py=1062
src/cadrumo/application/auth/operator_result_projections.py=197
exit 0
```
