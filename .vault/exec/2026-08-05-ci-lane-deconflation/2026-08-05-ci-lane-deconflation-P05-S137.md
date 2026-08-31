---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a13a3e4c1931dd5957f5becd19315d1df92c40aa872c87ddc35b9f84f9698267'
step_id: 'S137'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
## Changes

- `M` `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`
- `A` `src/cadrumo/application/auth/tests/test_certificate_sources_health.py`

## Notes

Verification evidence required by P05.S137:

```text
vaultspec-rag search 'certificate source check auth tests size budget real behavior' --type code
Refusing to search against the running service.
This vaultspec-rag client is 0.4.2 but the running service is 0.4.10.
exit 1

uv run --no-sync ruff check src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/application/auth/tests/test_certificate_sources_health.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/application/auth/tests/test_certificate_sources_health.py
2 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/application/auth/tests/test_certificate_sources_health.py
32 tests collected in 1.71s
exit 0
deselected 0

uv run --no-sync pytest -n 0 src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/application/auth/tests/test_certificate_sources_health.py
============================= 32 passed in 46.67s =============================
exit 0

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); targets=('src/cadrumo/application/auth/tests/test_certificate_sources_check.py','src/cadrumo/application/auth/tests/test_certificate_sources_health.py'); print('POLICY='+str(MODULE_POLICY.default_limit)); [print(path+'='+str(measures[path])) for path in targets]"
POLICY=1250
src/cadrumo/application/auth/tests/test_certificate_sources_check.py=1123
src/cadrumo/application/auth/tests/test_certificate_sources_health.py=223
exit 0
```
