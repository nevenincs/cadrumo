---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6398861b48ae19417444f58df07e23d8c5f9382603bfedc530bcf49992a37a22'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S53 composite relative closing review`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

Independently reviewed `W04.P07.S53` against the accepted generator-authority ADR, source-authority research, plan, S30 execution and audit, and the reconciled final S43 execution and audit. Fresh semantic discovery located the sole parser/schema authority in `src/cadrumo/domain/calculations/registry/_record_design.py` and `_record_design_schema.py`, the SHA-bound projection in `dev/registry/_record_design_ir.py`, exact preservation through `dev/registry/_semantic_map_join.py`, and fixed-generation refusal in `dev/registry/_export_tree.py`; targeted exact-symbol searches confirmed there is one composite-closing definition and constructor, no record-name/modelo/source selector, and no closing-row concatenation path.

The exact S53-owned review surface was the composite schema and parser hunks, the public registry-facade promotion, the intermediate schema-version and typed projection hunks, and the parser, source-boundary, intermediate, provenance-cutover, and real-generation-refusal tests. Concurrent changes in `dev/registry/_export_tree.py`, `dev/registry/_provenance_manifest.py`, unrelated registry-facade ordering, and S44/S45 vault and schema work were treated as peer-owned context and were not attributed to or modified by S53. The reviewed production blobs were `9640225d5f33faec0fd41b02569b2a5cec723304` for the schema, `6924a2f2a9fd3063e22d624f8070cf148052e577` for the parser, `918d03baf0a260c09cfaadd2274d7c651ce7a23d` for the IR, `de04ff1202c77d2984afbc699ecfb5aa1cba4fc3` for the join, and peer-context blob `adccc627339b5568c235319f31ab6284130c787b` for fixed-generation refusal.

All three pinned Modelo 220 binaries (`2023`, `2024`, and `2025`) resolve through catalogue applicability plus source SHA-256 and produce one typed `T220000000` envelope. Its six relative-closing rows retain exact source rows, workbook cells, ordinals, `***` offsets, lengths `(3, 3, 1, 4, 2, 5)`, alphanumeric types, descriptions, validation, and contents `("</T", "220", "(*)[A|E|I|0]", null, "0A", "0000>")` without joining. The parser refuses incomplete, duplicate/over-complete, reordered, and content-ambiguous composite shapes through the production validators. Body-led recognition and isolated mixed-total refusal preserve the final S43 contract: all registered sources, including the ten M131/M232/M390 partial-marker designs, remain parseable, while real M200 and all five M303 epochs retain their existing one-row closing envelopes.

The typed composition survives the public source-SHA-bound intermediate loader and semantic join. `RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION` advances from 2 to 3, and the provenance contract explicitly refuses obsolete parser schema versions 1 and 2. The existing fixed-width renderer receives the retained envelope, refuses before target creation, and emits no partial M220 tree. No legacy aliases, compatibility readers, inferred extents, fuzzy/positional matches, duplicate authorities, test doubles, skipped tests, or tautological business-logic copies were found.

Independent gates on the pinned S53-owned snapshot:

- Focused parser, source-boundary, IR, generation-refusal, and provenance suite: 72 passed with five upstream `openpyxl` conditional-formatting warnings in 60.19 seconds.
- Complete `dev/registry/tests` lane: 195 passed with three upstream `openpyxl` conditional-formatting warnings in 38.50 seconds.
- Scoped Ruff across all S53-owned production and test files: all checks passed.
- Scoped strict BasedPyright across the same files: 0 errors, 0 warnings, 0 notes.
- Structural anti-pattern search across the scoped tests: no mock, fake, stub, patch, monkeypatch, skip, or xfail patterns.
- After later concurrent registry-facade edits, the public `RecordDesignCompositeRelativeClosing` import probe, facade Ruff, and facade strict BasedPyright remained green.

A later broader `test_record_design*` retry against concurrently advancing S45 header-axis WIP produced 55 passes and 41 failures. All failure paths collapse while loading Modelo 111 because the new strict header enum rejects the current `presenter_nif`, `page_complementaria`, `colegio_concertado`, and `aeat_seal` tokens. Those files and semantics are outside S53, appeared after the green pinned S53 and complete development-registry lanes, and do not alter any reviewed S53-owned blob. The broader current shared-tree lane is therefore not claimed green; its red state is recorded as peer-WIP validation contamination, not an S53 defect.

## Findings

### s53-lifecycle-contract-drift | resolved-medium | Final S43 lifecycle evidence now records the authoritative body-led trigger

The initial S53 review found the checked S43 execution and audit still describing the rejected union trigger that treated standalone closers and Variable-total facts as decisive. That wording contradicted the current body-led parser and the real-source evidence that ten M131, M232, and M390 binaries legitimately contain partial markers. The lifecycle records were reconciled through hash-guarded VaultSpec CLI writes during this review. Their final blobs are `fa09f6d92900c61d7a1200123ad3eacc4261e42d` for the S43 execution record and `938b930cf07641332114eed7dc84e4787b7173f9` for the S43 audit. Both preserve the interim review trail, record its real-source refutation, and attest body-led recognition plus isolated mixed-total refusal. Re-reading those exact blobs closes the canonical-drift blocker.

No open findings remain in the S53 code or test payload.

## Recommendations

Accept `W04.P07.S53`. Preserve the exact six-part parser-owned M220 closing contract, source-SHA-bound lossless IR projection, schema-version hard cutover, body-led S43 recognition, M200/M303 single-closing behavior, all-source parseability gate, and pre-write fixed-generation refusal. Do not add a Modelo, sheet-name, source-reference, legacy-tree, inference, or concatenation selector for this shape. Keep the later S45 header-token failures with their owning peer work and do not use that contaminated broader lane to rewrite or widen S53.
