---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S03'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add typed-aggregation roundtrip and per-family default tests that fail if the typed op is dropped or a wrong family default is applied and ## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add typed-aggregation roundtrip and per-family default tests that fail if the typed op is dropped or a wrong family default is applied

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py`

## Description

- Add a domain-tests module asserting the typed-aggregation contract under the registry tests folder.
- Round-trip a `BindingAggregation` through the strict model for every registry-declared op value, hydrating the raw op string to its member and re-dumping back to the canonical value, plus a direct-member construction equality check.
- Assert the member set equals the complete registry-declared op set, enumerated independently from the sweep rather than derived from the enum.
- Assert the per-family default op via the accessor for each source family: the four detail-record families default to rows, every scalar-folding family defaults to sum, and an explicit op overrides the family default.
- Add the anti-tautology proof: corrupting the op to an unknown string, supplying a stray extra key, and omitting the op each raise a ValidationError; assert the model is frozen.

## Outcome

- The new module collects and passes (38 tests). The anti-tautology, extra-key, missing-op, and frozen assertions fail loudly if the typed boundary is ever weakened, so the round-trip assertions cannot become vacuous.
- The test asserts structure, validation, and the declared default mapping only — no hand-computed Decimal — per the no-tautological-calculation-tests discipline.

## Notes

- The schema-hygiene gate forbids the direct `DataBindingDefinition(` keyword constructor in test files. The binding fixture is built through `DataBindingDefinition.model_validate({...})` instead, which both satisfies the gate and validates the parametrised source string against the schema's closed source Literal (resolving a pyright Literal-narrowing error).
