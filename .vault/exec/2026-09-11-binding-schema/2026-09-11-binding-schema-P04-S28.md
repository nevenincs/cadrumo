---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:d43f512c997d74c66b4d48b5acc2f012d8358df930f1eac9f30d72f44dd87465'
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
- `M` `dev/registry/rename_formula_binding_identifiers.py` - edition-scoped rewrite (`rewrite_identifier_references_by_edition`, `edition_scoped_files`, `references_outside_rewritten_editions`, `ReferenceOutsideEditionError`); design-label and design-row-ordinal naming (`design_ordinal_identifier`, `_resolve_contested_names`); corpus-and-design evolutions generator (`repurposed_addresses`, `render_repurposed_evolutions`, `write_repurposed_evolutions`); `rewrite_in_files` as the single write path with read-back and a sha256/mtime manifest; `remove_emptied_fragment_directories` now proves ownership from this run's own removals instead of consulting version control.
- `M` `dev/registry/record_design_labels.py` - `RecordDesignRow.ordinal` and `design_field_text`.
- `A` `dev/registry/tests/test_modelo_714_residual_naming.py` - 6 cases against an independently derived oracle.
- `A` `dev/registry/tests/fixtures/modelo-714-residual-binding-renames.json`
- `A` `dev/registry/tests/fixtures/modelo-714-expected-identifier-evolutions.toml`
- `A` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2022/identifier_evolutions/0001-replaced-record-design-slot-repurpose.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/` - 120 edition-scoped renames across 50 files.
- `verify:` `uv run --no-sync python -m pytest dev/registry/tests/test_rename_span_strip.py dev/registry/tests/test_modelo_714_residual_naming.py -q` -> `30 passed`
- `verify:` `ruff check` + `ty check` on the four changed modules -> `pass`, `pass`
- `verify:` `... --strip-spans --modelo 714 --apply --write-manifest-dir ...` -> `exit 0; 240 references, 50 files, 10 evolution rows`
- `verify:` `load_modelo_directory('.../714')` -> `pass` for 2021-2025, 2022 carries 10 evolutions
- `verify:` `just report-registry-edition-delta-status --lines --totals-only` -> `family bindings address_identifiers=0`

## Notes

- Supersedes the notes above it. Every modelo 714 binding id now names its slot rather than its byte address: `address_identifiers` reads 0, down from 2126 at the start of this step. The name comes from the official record design's `Descripcion` for the row at the binding's own `(record, offset)` whose declared width equals the provider's length; where that label does not single a row out inside its record, or will not fit the identifier the loader accepts, the design's own row ordinal names it instead. Nothing is derived from an offset.
- The rewrite is edition-scoped. An identifier resolves inside the revision that declares it, so each edition's files are rewritten under that edition's own map, which is what lets `714-05` offset 290 be the 13-byte `Nº Valores 3` in 2021 and the 1-byte `Clave 3` from 2022. A guard refuses the pass if any file outside this modelo's editions quotes a renamed id; the generated address map is excluded by name, because it records the old spellings on purpose.
- Ten `replaced` identifier evolutions were generated from the designs and the corpus, not five as first estimated: four addresses were repurposed between the 2021 and 2022 designs while their bindings were already well named, so they were never rename candidates and a plan-derived list could not have seen them.
- Directory removal no longer consults version control. The pass records the files it removed and removes a directory only when it emptied it and a read-back shows it empty, which is self-contained and cannot be misled by an index state.
