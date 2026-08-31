---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3cc0fb7626bdc00cdb14db371062087948f5e9261895a8738ec230976ed61ba2'
step_id: 'S138'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
## Changes

- `M` `src/cadrumo/application/calculations/_relation_prefill.py`
- `A` `src/cadrumo/application/calculations/_relation_prefill_m202.py`
- `M` `src/cadrumo/application/calculations/__init__.py`

## Notes

Verification evidence required by P05.S138:

```text
vaultspec-rag search 'relation prefill calculation tests dependency identity source mapping' --type code
Refusing to search against the running service.
This vaultspec-rag client is 0.4.2 but the running service is 0.4.10.
exit 1

uv run --no-sync ruff check src/cadrumo/application/calculations/_relation_prefill.py src/cadrumo/application/calculations/_relation_prefill_m202.py src/cadrumo/application/calculations/__init__.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/calculations/_relation_prefill.py src/cadrumo/application/calculations/_relation_prefill_m202.py src/cadrumo/application/calculations/__init__.py
3 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/calculations/tests/test_relation_prefill_source_mesh.py
13 tests collected in 1.84s
exit 0
deselected 0

uv run --no-sync pytest -n 0 src/cadrumo/application/calculations/tests/test_relation_prefill_source_mesh.py
======================== 13 passed in 91.23s (0:01:31) ========================
exit 0

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, measure_module_lines; measures=measure_module_lines(); targets=('src/cadrumo/application/calculations/_relation_prefill.py','src/cadrumo/application/calculations/_relation_prefill_m202.py'); print('POLICY='+str(MODULE_POLICY.default_limit)); [print(path+'='+str(measures[path])) for path in targets]"
POLICY=1250
src/cadrumo/application/calculations/_relation_prefill.py=1237
src/cadrumo/application/calculations/_relation_prefill_m202.py=57
exit 0
```
