---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:13e4e9328622d4cf65d67cb807d2c3773f74f834693f75428d9b112c87c78ea1'
step_id: 'S140'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in diagnostics.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/diagnostics.py`

## Changes

- `M` `src/cadrumo/application/diagnostics.py`
- `A` `src/cadrumo/application/diagnostic_models.py`
- `M` `src/cadrumo/application/repair_integrity.py`
- `M` `src/cadrumo/application/tests/test_diagnostics.py`
- `M` `src/cadrumo/application/tests/test_diagnostics_dispatch.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_cli.py`
- `M` `src/cadrumo/tests/test_deferred_cross_layer_imports.py`

## Notes

```text
uvx vaultspec-rag search 'application diagnostics diagnostic reporting observability only:prod' --type code
Refusing to search against the running service.
This vaultspec-rag client is 0.4.2 but the running service is 0.4.10.
exit 1

uv run --no-sync ruff check src/cadrumo/application/diagnostics.py src/cadrumo/application/diagnostic_models.py src/cadrumo/application/repair_integrity.py src/cadrumo/application/tests/test_diagnostics.py src/cadrumo/application/tests/test_diagnostics_dispatch.py src/cadrumo/entrypoints/cli/_config/_repair_cli.py src/cadrumo/tests/test_deferred_cross_layer_imports.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/diagnostics.py src/cadrumo/application/diagnostic_models.py src/cadrumo/application/repair_integrity.py src/cadrumo/application/tests/test_diagnostics.py src/cadrumo/application/tests/test_diagnostics_dispatch.py src/cadrumo/entrypoints/cli/_config/_repair_cli.py src/cadrumo/tests/test_deferred_cross_layer_imports.py
7 files already formatted
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/tests/test_diagnostics.py src/cadrumo/application/tests/test_diagnostics_dispatch.py src/cadrumo/tests/test_deferred_cross_layer_imports.py src/cadrumo/entrypoints/cli/_config/tests/test_config_repair_profile_integrity_payloads.py
74 tests collected in 2.32s
No marker selector or --deselect option was supplied; deselected 0.
exit 0

uv run --no-sync pytest -n 0 -q src/cadrumo/application/tests/test_diagnostics_dispatch.py
16 errors in 3.74s
ImportError: cannot import name 'default_ecb_rate_provider' from 'cadrumo.adapters.outbound.fx'
The failure occurs in the shared conftest runtime-port fixture before diagnostics test execution, through application.invoices._creation. It is outside S140 ownership.
exit 1

uv run --no-sync python -c "from cadrumo.application.diagnostic_models import DiagnosticCheck; from cadrumo.application.diagnostics import build_cli_version_report, render_cli_version_text; check=DiagnosticCheck(name='probe', status='ok', summary='ok'); report=build_cli_version_report(with_registry=False); assert check.precondition_verdict is None; assert report.registry.available is False; assert 'cadrumo' in render_cli_version_text(report); print('DIAGNOSTIC_MODEL_AND_VERSION_PROBE=PASS')"
DIAGNOSTIC_MODEL_AND_VERSION_PROBE=PASS
exit 0

uv run --no-sync python -c "from cadrumo.tests import MODULE_POLICY, CALLABLE_POLICY, measure_module_lines, measure_callable_lines; m=measure_module_lines(); c=measure_callable_lines(); targets=('src/cadrumo/application/diagnostics.py','src/cadrumo/application/diagnostic_models.py'); print('MODULE_POLICY='+str(MODULE_POLICY.default_limit)); [print(path+'='+str(m[path])) for path in targets]; print('CALLABLE_POLICY='+str(CALLABLE_POLICY.default_limit)); [print(key+'='+str(c[key])) for key in sorted(c) if key.startswith('src/cadrumo/application/diagnostics.py::') and c[key] > 120]"
MODULE_POLICY=1250
src/cadrumo/application/diagnostics.py=1135
src/cadrumo/application/diagnostic_models.py=231
CALLABLE_POLICY=180
src/cadrumo/application/diagnostics.py::build_config_repair_report=155
exit 0

uv run --no-sync python -m dev.audit.size_budget
size budget: scanned 5640 modules, 15608 production callables.
size budget: FAIL - 78 finding(s).
S140's diagnostics.py subject is absent from the 53 module and 22 callable over-budget findings; the remaining findings belong to other plan rows or concurrent work.
exit 1
```

## Repair verification

```text
uv run --no-sync ruff check src/cadrumo/application/diagnostics.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/diagnostics.py
1 file already formatted
exit 0

uv run --no-sync python -c "import ast, pathlib; path=pathlib.Path('src/cadrumo/application/diagnostics.py'); tree=ast.parse(path.read_text(encoding='utf-8')); relocated={'CliVersionReport','ConfigRepairReport','DiagnosticCheck','DiagnosticFinding','DiagnosticStatus','RegistryIntegrityReport','RegistryVersionSummary','SecureObjectIntegrityReport','ensure_models_rebuilt'}; found=sorted({node.id for node in ast.walk(tree) if isinstance(node,ast.Name) and node.id in relocated}); assert not found, found; import cadrumo.application.diagnostics as module; exposed=sorted(name for name in relocated if hasattr(module,name)); assert not exposed, exposed; print('OLD_DIAGNOSTICS_CONTRACT_BINDINGS=0')"
OLD_DIAGNOSTICS_CONTRACT_BINDINGS=0
exit 0

uv run --no-sync python -m compileall -q src/cadrumo/application/diagnostics.py
exit 0

uv run --no-sync pytest -n 0 --collect-only -q src/cadrumo/application/tests/test_diagnostics.py src/cadrumo/application/tests/test_diagnostics_dispatch.py
55 tests collected in 3.28s
No marker selector or --deselect option was supplied; deselected 0.
exit 0

uv run --no-sync pytest -n 0 -q src/cadrumo/application/tests/test_diagnostics_dispatch.py
16 passed in 3.93s
exit 0

uv run --no-sync pytest -n 0 -q src/cadrumo/application/tests/test_diagnostics.py src/cadrumo/application/tests/test_diagnostics_dispatch.py
.....
The host command window ended before pytest emitted an exit status; no failure was reported in the captured partial output.
exit unavailable
```
