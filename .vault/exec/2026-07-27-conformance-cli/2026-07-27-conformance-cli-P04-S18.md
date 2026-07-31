---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:751297cde933d14833dd64c7131cf38e66c9c0a4fbd46d43a14adc9b618afeea'
step_id: 'S18'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add the dev-path isolation gate asserting no shipped module imports dev.* or embeds a dev/ path literal, with an injectable-root anti-tautology proof

## Scope

- `src/cadrumo/tests/test_dev_path_isolation.py`

## Description

- Read plan, ADR, and research in full; confirmed step is independent with no peer-contended files.
- Ran mandatory RAG probes for "dev path isolation gate shipped module import boundary" and "dev tooling import shipped module violation src cadrumo"; results confirmed `dev/import_hygiene_scan.py` as the canonical prior art.
- Pre-scan verified zero pre-existing violations: 1398 shipped modules, 0 dev.* imports, 0 dev/ path literals.
- Authored `src/cadrumo/tests/test_dev_path_isolation.py` as a self-contained gate (no `dev.*` imports) implementing two inline scanners: `find_dev_import_violations` (AST import + dynamic `importlib.import_module` literal) and `find_dev_path_literal_violations` (string constant prefix scan).
- Resolved scope to shipped modules (test trees excluded from wheel may legitimately import dev tooling; consistent with the existing Family-5 ruling in `test_import_hygiene_gate.py`).
- Self-contained constraint resolved by re-implementing the detection logic inline from `dev/import_hygiene_scan.py` without importing it; the gate itself is its own conformance proof.
- Applied ruff format; fixed two RUF059 unused-unpack variables (`_lineno`); fixed pyright error by adding `isinstance(node.value, str)` guard in the path-literal scanner.
- Committed as `43d7ab1e60` with explicit pathspec.

## Outcome

All 11 tests pass (24 s, 6 workers):

- `test_no_shipped_module_imports_dev_tooling` — PASSED; vacuity floor 1398 shipped modules (floor 500); 0 violations.
- `test_no_shipped_module_embeds_dev_path_literal` — PASSED; same module count; 0 violations.
- `test_import_scanner_catches_planted_static_dev_import` — PASSED; `"from dev.registry.matrix import manager"` detected.
- `test_import_scanner_catches_bare_dev_import` — PASSED; `"import dev"` detected.
- `test_import_scanner_catches_planted_dynamic_dev_import` — PASSED; `importlib.import_module("dev.registry.matrix.manager")` detected.
- `test_import_scanner_does_not_fire_on_excluded_test_module` — PASSED; ruling pinned: test trees are not violations.
- `test_import_scanner_does_not_fire_on_cadrumo_import` — PASSED; `cadrumo.*` imports do not over-trigger.
- `test_path_literal_scanner_catches_planted_dev_path` — PASSED; `"dev/import_hygiene_baseline.json"` detected.
- `test_path_literal_scanner_catches_relative_prefix_forms` — PASSED; `"./dev/"` and `"../dev/"` both detected.
- `test_path_literal_scanner_does_not_fire_on_path_join_usage` — PASSED; `Path(root) / "dev" / "file"` is not a literal violation.
- `test_path_literal_scanner_does_not_fire_on_excluded_test_module` — PASSED; ruling pinned for path-literal check too.

Ruff clean; pyright 0 errors. No pre-existing violations found.

## Notes

The self-contained constraint (gate must not import dev.*) was the key design challenge. Resolution: inline re-implementation of the AST scanner logic from `dev/import_hygiene_scan.py`, reading the packaging exclude globs from `pyproject.toml` directly via `tomllib`. The `test_import_hygiene_gate.py` in the same directory imports `dev.*` and continues to do so (it is a test file, excluded from the wheel, and that import is the Family-5 check's own dependency on the scanner it gates). The new gate covers shipped modules only, consistent with the Family-5 ruling. The `Path("...") / "dev" / "..."` join form is correctly excluded from the path-literal check (not a "dev/" prefixed literal).
