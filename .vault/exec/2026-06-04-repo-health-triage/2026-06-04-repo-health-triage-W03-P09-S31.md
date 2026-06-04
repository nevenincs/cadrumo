---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
step_id: 'W03.P09.S31'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace {feature} with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# W03.P09.S31 - Extract formula initial-value materialization

Scope: execute the registry runtime decomposition step for formula initial-value materialization.

## Description

- Add `_formula_initial_values.py` for formula input state assembly.
- Move `initial_values`, `materialise_observations`, previous-filing absent-by-design detection, and binding-selector projection into the new module.
- Keep `_formula_runtime.py` as the calculation dispatcher and import the extracted helpers under the existing private names.
- Preserve runtime diagnostics for unknown inputs, computed-casilla input rejection, previous-filing smuggling, inconsistent previous-filing projection, missing previous-filing binding values, and absent-by-design observations.

## Outcome

- `_formula_runtime.py` dropped from 1280 lines to 1064 lines.
- `_formula_initial_values.py` landed at 171 lines.
- Focused runtime and reviewability gates passed.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_formula_initial_values.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_registry_reviewability.py`
  - `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_130_registry.py::test_modelo_130_first_period_carry_forward_is_absent_by_design src/aeat/domain/calculations/registry/test_modelo_130_registry.py::test_modelo_130_previous_filing_bound_casilla_input_without_binding_value_is_rejected src/aeat/domain/calculations/registry/test_modelo_130_registry.py::test_modelo_130_previous_filing_bound_inputs_must_match_binding_values src/aeat/domain/calculations/registry/test_formula_runtime.py -q`
  - `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_modelo_130_registry.py -q`
  - `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
