---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S03'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
---

# `schema-hardening-m130-standardization` `P01.S03`

Verified the M130 directory split and repaired stale regression assumptions that
still treated M130 as a single-file TOML or casilla 15 as manual input.

- Modified: `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`

## Description

The broader registry gate surfaced two edges:

- File-loader mutation tests hardcoded `modelos/130.toml`; they now build a
  temporary single-file fixture from the committed M130 directory fragments.
- Formula/runtime tests supplied bound carry-forward casillas as manual inputs;
  they now provide those values through `binding_values`, preserving the current
  registry contract that bound casillas cannot be supplied as inputs.

M130 discovery now reports one fragment-directory revision with 16 fragments.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `208 passed in 112.80s`
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py`
