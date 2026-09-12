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
- `M` `dev/registry/rename_formula_binding_identifiers.py` - no member id may carry its provider offset in ANY spelling: `drop_provider_offset_tail` removes a trailing separator-bounded token equal to `str(provider.offset)` or the `<offset>-<offset+length-1>` remnant, repeating while both are stacked, and runs after the full-`provider.field` restoration that re-introduced the address. An unexplained span-shaped run elsewhere in the id no longer vetoes the tail drop. Adds `remove_emptied_fragment_directories` (git-status-gated, refuses a dirty directory) and `write_address_map`, which records every candidate's `old_id`/`new_id`/`record`/`offset`/`length`/`field` before any address is dropped.
- `A` `dev/registry/generated/714-binding-id-address-map.json` - 2,121 candidates, generated, not hand-edited.
- `M` `dev/registry/tests/test_rename_span_strip.py` - 8 added cases: bare-offset tail with no span run, restored-field re-statement, a trailing number that is not the address, offset-only sibling slots refusing the modelo whole, mid-word truncated prefixes colliding on the post-image, an unexplained run not vetoing the tail drop, emptied-directory removal, and a dirty emptied directory left in place.
- `verify:` `uv run --no-sync python -m pytest dev/registry/tests/test_rename_span_strip.py -q` -> `15 passed`
- `verify:` `uv run --no-sync ruff check` + `ty check` on both files -> `pass`, `pass`
- `verify:` `... --strip-spans --modelo 714 --dry-run` -> `exit 1; 2121 candidates, 160 within-edition collisions, modelo refused whole`
- `verify:` `... --strip-spans --modelo 714 --apply` -> `exit 1; address map written, 0 references rewritten, corpus unchanged`
- `verify:` `load_modelo_directory('src/cadrumo/_data/registry/aeat/modelos/714')` -> `pass`
- `verify:` `just report-registry-edition-delta-status --lines --totals-only` -> `family bindings address_identifiers=2126` (unchanged; 714=2121, 390=5)

## Notes

- The extended rule is implemented and proven, and it REFUSES modelo 714 whole. 714's `provider.field` values for these rows are themselves the offset (`...inst-invers-290` at offset 290), so the offset-free name is shared by every slot of the enclosing record block: 32 collision groups per edition, 160 across the chain, 2,116 of 2,121 candidates withdrawn. Re-appending an offset to disambiguate is the restatement the rule exists to remove, so nothing was applied and the corpus is byte-unchanged.
- No `identifier_evolutions` row was authored. Eleven `(record, offset)` pairs and eight same-id rows change field, length, data type or channel across the 2021 -> 2022 edge, including `714-05` offset 290 (money/decimal length 13 -> text/text length 1), offset 843 (text length 20 -> integer length 5) and `714-05` offset 1551 (text length 20 -> money/decimal length 13). Each needs the governing record design, and `corpus/aeat_official/disenos_registro/modelo_714/files/DR714_2021..2025.xls` - the sources the revisions cite as `aeat-dr-714-YYYY` - are not present in this repository. All are listed as needs-design-evidence rather than guessed.
- Modelo 390 carries the same spelling on 5 binding ids (2024 edition) with 0 collisions and 0 stranded export trees; it was left unapplied as outside this pass's file scope.
