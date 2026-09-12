---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:878f438a7c606658dde05dab70eeff050c9cd73929fe1d745412e1c243edaeaa'
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
- `A` `dev/registry/record_design_labels.py` - reads an AEAT record design's own `Descripcion` column out of its extracted sidecar, keyed by `(record, offset)`; resolves the sidecar through the registry's own citation chain and hashes the binary against the declared `sha256` before trusting it.
- `M` `dev/registry/rename_formula_binding_identifiers.py` - the design label, where it proves the row, names the slot; `binding_identifier_limit` reads the cap off the shipped `BindingId`; `_withdraw_edition_divergent_names` isolates an id its editions would name two ways; within-edition collisions now withdraw the contested renames and `_surviving_collisions` re-projects as the injectivity proof; `rewrite_identifier_references` reads every write back and raises `WriteNotObservedError` on mismatch, optionally emitting a per-file sha256 manifest via `--write-manifest-dir`.
- `M` `dev/registry/tests/test_rename_span_strip.py` - 12 added cases across the offset-tail rule, design-label reading, the header-driven column lookup, the strict decode, emptied-directory removal and its dirty refusal.
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/` - 628 binding ids renamed from their record design's field labels, 4002 references rewritten, 105 files.
- `A` `dev/registry/generated/714-binding-id-address-map.json` - the durable pre-rename map.
- `verify:` `uv run --no-sync python -m pytest dev/registry/tests/test_rename_span_strip.py -q` -> `19 passed`
- `verify:` `uv run --no-sync ruff check` + `ty check` on the three changed modules -> `pass`, `pass`
- `verify:` `... --strip-spans --modelo 714 --apply --write-manifest-dir ...` -> `exit 0; 628 ids, 4002 references, 105 files, 0 surviving collisions`
- `verify:` `load_modelo_directory('src/cadrumo/_data/registry/aeat/modelos/714')` -> `pass` for 2021-2025
- `verify:` `just report-registry-edition-delta-status --lines --totals-only` -> `family bindings address_identifiers 2126 -> 120`

## Notes

- Supersedes the note above it. The 714 record designs are present in this repository under the corpus root, and all five hash-match the `sha256` the registry declares, so the slot names the ingestion never recorded were recovered from the designs rather than guessed. The rule is: for a binding whose id ends in its own provider offset, the name is the design's `Descripcion` for the row at that `(record, offset)` whose declared width equals the provider's length, appended to the block prefix the corpus already spells. No name is derived from an offset.
- 628 of 661 bare-offset ids are renamed. The 33 that remain are withdrawn by the post-image gate and each is classified. Five are one identifier covering two different fields across the 2021 -> 2022 edge - `714-05` offsets 74, 290, 843 and 1551 and `714-06` offset 70 - which a textual rename cannot express and which need an `identifier_evolutions` `replaced` row citing both designs; none was authored here, since that is an authoring act rather than a spelling change. The other 28 are addresses whose design row either shares its label with another row of the same record - the 2021 design labels both `714-02` offset 40 and offset 42 "Situacion 1" - or declares no row of matching width there.
- Collisions withdraw the contested renames and are listed; they no longer withdraw the whole modelo. An offset is never re-appended to separate two names, because that is the restatement the rule exists to remove.
