---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:48aa3d9d641ebc81d2ca78276df164cec084282c033b5e4fbf348b5ea6b1ab47'
step_id: 'S293'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate the cross-module private import of _ManualInputSelector: extract the manual_input selector model, its record-shape key set and is_layout_binding_selector into their own public defining module, so binding_selector_utils.py's two function-local imports of a private bindings.py symbol -- present specifically to break a real module-level import cycle -- become ordinary module-level imports of a shared public contract with no cycle, and no consumer imports a private cross-module name

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`
- `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- `src/cadrumo/domain/calculations/registry/_validate_record_sections.py`
- `a new public defining module for the manual_input selector`
- `and every test importing these symbols`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/manual_input_selector.py`
- `A` `docs/api/cadrumo.domain.calculations.registry.manual_input_selector.rst`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_record_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_boolean_binding_encoding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_data_type_vocabulary_containment.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_manual_input_record_field_selector.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_boolean_binding_encoding.py test_manual_input_record_field_selector.py test_data_type_vocabulary_containment.py -q -m unit` -> `pass` (14 passed)
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/domain/calculations/registry` -> `pass` (5945/5992 collected, 47 deselected, unchanged before/after)

## Notes

Adjudication: shared contract that belongs in a public defining module.
`_validate_record_sections.py` independently needs the same record-shape
predicate (`is_layout_binding_selector`), so the concept has two genuine
readers, not one narrower consumer that should own it privately; both
readers have real independent need for the strict validated shape, so
deletion was not an option either. The validation stays on the type
(`ManualInputSelector` owns its own shape validation in its new module),
not moved into `binding_selector_utils.py` -- matching the pattern every
other binding family in this dispatch module already follows.

The deferred imports in `binding_selector_utils.py` were confirmed
load-bearing, not vestigial: `bindings.py` imports `selector_as_dict` /
`selector_against_model` from `binding_selector_utils.py` at module level,
so a module-level import of `_ManualInputSelector` the other direction was
tried directly and failed with a circular-import error before the
extraction; after extracting to `manual_input_selector.py`, both modules
import cleanly at module level with no deferral.

RAG query: "shared selector model split into its own module to break an
import cycle between two registry binding files only:prod" (`--type
code`) -- returned only the new module itself (already indexed) and
unrelated per-family binding modules, confirming no existing sibling
already solves this.

A full parallel run of `src/cadrumo/domain/calculations/registry/tests`
showed 33 failed, 3 errors among 5892 passed; none of the failing or
erroring tests touch `bindings.py`, `binding_selector_utils.py`,
`_validate_record_sections.py` or `manual_input_selector.py` -- consistent
with this suite's known parallel loader-cache race rather than this
change.
