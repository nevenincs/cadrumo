---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Verify W01.P01 no-shift: run pytest --collect-only -q clean, the docstring-core-struct gate green, and the bindings-framework gate suite green and ## Scope

- `assert pure-rename with no semantic / type-value change across the BindingRow renames`
- `src/aeat/domain/calculations/registry/tests`
- `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
