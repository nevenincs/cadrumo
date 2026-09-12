---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:cf33ff9fd1e31b93eb1d6a6ec7edf762debaf5e38f00f29b877f1de7dc8c9c26'
step_id: 'S28'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Modelo 714: restore the full provider.field slot (which carries the repetition) into its 4,844 span-bearing binding ids through a rename-tool rule with per-row address proof and a cross-edition collision gate (0 in all five editions), rewriting references and regenerating export trees in the same run; the generator needs no change

## Scope

- `dev/registry/pipeline/_export_tree.py`
- `dev/registry/mappings/modelo_714/`
- `src/cadrumo/_data/registry/aeat/modelos/714/`

## Changes

- `M` `dev/registry/rename_formula_binding_identifiers.py`
- `M` `dev/registry/tests/test_binding_span_strip.py`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_binding_span_strip.py -n 0` -> `pass`
- `verify:` `uv run ty check dev/registry/rename_formula_binding_identifiers.py dev/registry/tests/test_binding_span_strip.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/rename_formula_binding_identifiers.py dev/registry/tests/test_binding_span_strip.py` -> `pass`

## Notes

The modelo 714 identifier pass is planned but not applied: the dry run reports
4844 strips, 1415 rename pairs, 0 refusals, 0 collisions and 0 stranded export
trees, and the apply, the revision regeneration and the delta-status report are
deferred to a later run. No registry data was rewritten.

The Step was scoped to a record-design-derived repetition index in the export
tree generator. Measurement showed no generator produces these ids and no index
needed deriving: the repetition is already carried by each row's own
`provider.field`, and 153 ids merely spell a separator-bounded truncation of it.
The rule therefore restores the declared field and lives in the rename tool; the
generator and its mappings are unchanged, so the Scope paths above are stale.
