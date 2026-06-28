---
tags:
  - '#audit'
  - '#registry-formula-runtime-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-formula-runtime-boundary` audit: `formula runtime extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_formula_runtime.py` as
the registry calculation engine and a large production module with broad
consumers across filing, verification, CLI, Google Sheets, and
continuity tests.

## Findings

### High

- `_formula_runtime.py` is 1,265 working-tree lines and combines public
  calculation result models, M210 sentinel constants, the
  `calculate_registry_snapshot` entry point, initial-value projection,
  previous-filing bound-casilla guards, expression dispatch, parameter
  and bracket resolution, M210 rate resolution, rounding, type guards, and
  public `read_parameter`.
- The file has no local diff at audit time, so it is a reasonable
  near-term implementation target after audit closure.
- The public registry API re-exports `calculate_registry_snapshot`,
  `RegistryCalculationEntry`, `RegistryCalculationResult`,
  `read_parameter`, and the M210 sentinel constants. Extraction must
  preserve those imports and result-model serialization behavior.
- `_formula_runtime.py` imports `_PreviousModeloSelector` from
  `_bindings.py` for previous-filing absent-by-design checks. That
  private dependency was also flagged in the binding boundary audit. It
  should not be moved casually while previous-filing resolver work is
  active.

### Medium

- Public entry orchestration is a cohesive family:
  `calculate_registry_snapshot`, `RegistryCalculationEntry`,
  `RegistryCalculationResult`, observation materialisation, rounding, and
  external-value validation. This should remain in `_formula_runtime.py`
  until helper families are extracted.
- Initial values and previous-filing projection guards are a separate
  family. They are tightly coupled to `_PreviousModeloSelector`,
  `DataBindingDefinition`, and silent-zero regression prevention; extract
  them only after the previous-filing WIP has landed.
- Recursive expression evaluation is a cohesive family:
  `_EvalContext`, `_evaluate_expression`, `_evaluate_with_ctx`,
  arithmetic/comparison dispatch, leaf evaluation, and argument guards.
  This is the safest first implementation slice because it is pure engine
  logic and already has focused tests.
- Parameter and bracket lookup are a cohesive family:
  `_resolve_parameter`, `_resolve_bracket`, lookup-by-CCAA, lookup by
  entity type, and public `read_parameter`. Extracting the private lookup
  helpers is safe only if `read_parameter` remains public and delegates
  through the same implementation.
- M210 rate resolution is a coherent but domain-specific formula-op
  family. It should move after the generic evaluator split so the sentinel
  constants and verification rewrite contract stay obvious.

### Low

- Tests import some private evaluator helpers directly, especially
  `_evaluate_expression`. A first extraction should preserve a
  compatibility re-export from `_formula_runtime.py` or update tests in
  the same commit with no behavior change.

## Recommendations

1. Keep `_formula_runtime.py` as the public compatibility facade during
   staged decomposition.
2. First safe extraction candidate: recursive expression evaluation and
   arithmetic/comparison dispatch. Preserve `_evaluate_expression` as a
   private compatibility re-export while tests still import it directly.
3. Second extraction candidate: parameter and bracket lookup helpers.
   Keep `read_parameter` public and delegating through the same helper.
4. Third extraction candidate: M210 rate-resolution op and sentinel
   helpers. Keep public sentinel aliases in `_formula_runtime.py` and
   registry-root exports stable.
5. Defer initial-value and previous-filing absent-by-design extraction
   until `_PreviousModeloSelector` ownership is settled by the binding
   resolver work.
6. Do not split by modelo. Formula runtime modules must be generic engine
   families or generic named-op families.
7. Each extraction commit should run `test_formula_runtime.py`,
   `test_if_then_else_short_circuit.py`,
   `test_lookup_bracket_by_ccaa.py`,
   `test_lookup_bracket_by_entity_type.py`,
   relevant M200/M210 formula tests, public API boundary tests, and at
   least one committed-registry calculation test.

## Codification candidates

- **Source:** finding High-3.
  **Rule slug:** `registry-formula-runtime-facade`.
  **Rule:** Formula runtime decomposition must preserve the public
  calculation facade and split only generic engine or named-op families,
  never modelo-specific runtime modules.
