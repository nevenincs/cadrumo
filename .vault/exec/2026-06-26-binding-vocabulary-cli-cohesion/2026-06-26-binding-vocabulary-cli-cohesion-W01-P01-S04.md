---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-30'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W01.P01 no-shift: run pytest --collect-only -q clean, the docstring-core-struct gate green, and the bindings-framework gate suite green

## Scope

- `assert pure-rename with no semantic / type-value change across the BindingRow renames`
- `src/aeat/domain/calculations/registry/tests`
- `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`

## Description

- Run the bindings-framework gate suite (mesh-parity, source-kind taxonomy, aggregation, build-validation, pull-vs-calculate parity, binding-value provenance roundtrip) plus the CLI registry surface tests.
- Run the docstring-core-struct links gate, which the `_schema.py` `:class:` cross-reference update touches.
- Run collect-only over the full `src/aeat` tree and the apidocs scaffold drift check.

## Outcome

W01.P01 no-shift proven. The bindings-framework gate suite plus the CLI registry surface test ran 98 passed (86 deselected). The docstring-core-struct gate ran 3 passed. Collect-only is clean at 16461 collected (baseline-equal), and apidocs scaffold reports the stub tree conformant with no drift. Both `BindingRow` renames (A1, A3) are confirmed pure-rename with no semantic, type-value, or mechanism change.

## Notes

None.
