---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:f4fd23a90f924b7947a3215bc20ff54d960ec9e9bf20da28b223068edfe15a10'
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
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/`
- `verify:` `uv run --no-sync python dev/registry/rename_formula_binding_identifiers.py --strip-spans --modelo 714` -> `4844 candidates, 1415 rename pairs, 0 refused, 0 collisions, 153 restored-field rows`
- `verify:` `uv run --no-sync python dev/registry/rename_formula_binding_identifiers.py --strip-spans --modelo 714 --apply` -> `9688 references rewritten, 160 files touched`
- `verify:` `load_modelo_directory('src/cadrumo/_data/registry/aeat/modelos/714')` -> `pass`
- `verify:` re-measure after apply -> `0 binding ids, 0 candidates`

## Notes

- The 714 pass is applied: 4,844 span ids stripped under the full-provider.field slot rule (153 restored slots), 9,688 references rewritten across 160 files, 0 collisions in all five editions, load-verified; 714 has no generated export tree. The machine-filled Scope paths naming the export generator are stale: the generator needed no change.
