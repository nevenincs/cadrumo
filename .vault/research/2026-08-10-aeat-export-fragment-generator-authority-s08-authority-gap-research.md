---
tags:
  - '#research'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b16e45e74d4bdbd0c4b8058041cd31c7f4e3dcf30d11683c78cd7199b893b3a4'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s08-independent-review-audit]]"
---
# `aeat-export-fragment-generator-authority` research: `S08 record-design authority gap`

The exact hash-pinned Modelo 200/2025 workbook contains usable integer totals for 76 fixed-length sheets, but the shipped parser drops them because AEAT labels those rows `Total:` rather than `Total`. The remaining `DP200000` wrapper declares a variable-length body and has no integer total. The numeric-content gap is different: all 5,676 reported omissions are empty in the binary's field-level `Contenido` cells, not parser loss. The workbook supplies a source-wide amount-format note and per-row type, length, and description clues, but those clues do not constitute an exact per-field wire interpretation. A parser correction can recover the 76 totals; complete Modelo 200 rendering still requires the ADR to authorize a separately reviewed, source-hash-pinned numeric-format authority or to keep refusing this target.

## Findings

### Seventy-six declared totals are present and lost solely because of punctuation

The selected catalogue entry pins a 2,316,549-byte XLSX at SHA-256 `a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505`; a fresh local digest matched that value. Its 77 record-design sheets all use row 5 headers containing `Contenido`. Seventy-six sheets end with `Total:` in column A and a column-C `SUM` formula whose cached integer equals the terminal parsed offset. Examples are 627 at `DP200001!A119:C119` and 774 at `DP200DID!A49:C49` in the pinned workbook.

The XLSX parser opens cached values and does find the `Contenido` header, but `_total_positions_from_row` accepts only a normalized cell exactly equal to `total`; the colon remains after normalization. The IR then projects the resulting `None` without reinterpretation. This is a narrow parser defect: accepting the official `Total:` spelling would recover 76 of 77 declared totals without adding an authority.

### `DP200000` is a genuinely variable wrapper, not a missing integer-total case

`DP200000!A14:C16` states a variable-length embedded declaration: row 14 begins at 329 with length `Variable`, row 15 uses offset `***`, and its total row contains `Variable`, not an integer. The fixed-width parser necessarily excludes the non-integer rows and currently projects the preceding eight fixed fields ending at byte 328. Inferring 328 as the record total would contradict the workbook because the wrapper explicitly continues with variable content and a closing tag.

S08 therefore has a second real-target issue even after the punctuation fix. The ADR must settle whether `DP200000` is an envelope/composition instruction outside the generated record set, or whether the source and IR contracts gain an explicit variable-layout representation. An anomaly exception cannot safely turn it into a fixed record under the accepted constraint that exceptions do not supply coordinates.

### The 5,676 missing numeric `Contenido` values are absent at field level

The shipped parser and IR agree on 77 sheets, 6,808 fields, and 5,996 numeric fields. Of those numeric fields, 320 have non-empty `Contenido`; the other 5,676 have empty raw content cells in both formula and cached-value views. An `openpyxl@3.1.5` census found zero content formulas, comments, merged-cell anchors, or hidden-row/hidden-column values for those 5,676 cells. The workbook has 418 merged ranges overall, but none intersects a missing numeric content cell. The one unexpected value outside recognized columns was whitespace at `DP200009!H27`, not format metadata. The parser reads the correct content column and faithfully projects these blanks.

The omissions divide into 5,550 width-17 fields (3,323 `Num`, 2,227 `N`) and 126 other fields: 91 width 1, 11 width 2, 9 width 4, 10 width 5, 2 width 8, 2 width 9, and 1 width 13. The smaller fields include flags, month/day/year components, percentage fields, dates, telephone numbers, and an identifier; type and width alone do not distinguish integer, date, enumerated, percentage-decimal, or digit-string behavior.

### A workbook-wide note is useful evidence but not a complete field authority

The pinned workbook says at `DP200001!A121` that amounts use 15 integer digits, or `N` plus 14 integer digits, and 2 decimal digits. That can ground a reviewed source-specific convention for the 5,550 blank width-17 fields if the reviewer also establishes that each affected anchor is an amount and defines the `N` sign representation. It is not an exact field mapping: 148 of those fields lack bracketed casilla identifiers, and only 257 descriptions literally contain `importe`.

The workbook itself demonstrates why an unreviewed `type + length` default is insufficient. Non-empty `Num`/17 entries include `15 enteros y 2 decimales`, `Nota 1`, and `No cumplimentar`; non-empty `N`/17 entries include `15 enteros y 2 decimales`, `Nota 1`, and `Nota 2`. Styling also cannot resolve the gap: 18 style signatures are shared by blank cells and cells with different explicit content meanings. Treating every blank numeric field as an unsigned decimal or integer would therefore add a fact not stated at that exact anchor and would mishandle the note's signed `N` form.

### A parser fix is necessary but cannot make the target renderable

A parser change that recognizes the official `Total:` spelling is directly supported and preserves the current authority split. It should retain the formula's cached integer and prove equality with terminal extent. It cannot invent an integer for `DP200000`, and it cannot fill any of the 5,676 empty numeric content cells. The current renderer is consequently correct to refuse missing declared totals and unambiguous numeric forms; the synthetic tests prove that refusal but do not resolve the source gap.

A source-hash-pinned per-design render profile is the most localized candidate for the missing wire facts. It could bind reviewed global conventions and exact-anchor exceptions to this SHA-256 while leaving semantic maps meaning-only. This option requires an ADR amendment because the current profile owns only irreducible transport settings, while the accepted ADR says the official design owns every wire characteristic. The amended contract would need complete anchor coverage, explicit `Num` versus signed `N` handling, provenance digests, and refusal of every uncovered field.

Extending the semantic map with per-anchor numeric format would also make every interpretation reviewable and bijective, but it crosses the current rule that renderer formatting is intentionally absent from semantic entries. It would duplicate source wire shape beside registry meaning and therefore also requires an ADR amendment. It is the stronger option only if field meaning is necessary to decide format and a source-wide profile cannot express the exceptions without becoming a second semantic map.

Refusing Modelo 200/2025 remains the only outcome authorized by the current ADR after the parser fix. It is not a permanent product choice: it is the fail-closed state until the variable wrapper and numeric-format authority are reviewed. Neighbouring generated/manual trees and extracted derivatives were intentionally not consulted as correctness oracles.

### The ADR must settle two authority questions before S08 resumes

The amendment must determine, first, whether `DP200000` is excluded as a workbook composition wrapper or represented as a typed variable envelope. Second, it must choose the single reviewed home for numeric wire interpretation: a source-SHA-pinned render profile with exhaustive exact-anchor coverage, or an expanded semantic map. It must state whether `DP200001!A121` governs all 5,550 blank width-17 fields, define `N` sign encoding, ground the remaining 126 anchors, and require mutation gates proving that missing, conflicting, or hash-drifting rules refuse the whole design. Until those questions are decided, neither parser inference nor a renderer default can satisfy the accepted authority boundary.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/is.toml:1222`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_200/files/01-200-ejercicio-2025-10-9-mb-xls.xlsx`, SHA-256 `a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505`; cells `DP200000!A14:C16`, `DP200001!A119:C124`, and `DP200DID!A49:C49`
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR200e25.xls
- `src/cadrumo/domain/calculations/registry/_record_design.py:132`
- `src/cadrumo/domain/calculations/registry/_record_design.py:298`
- `src/cadrumo/domain/calculations/registry/_record_design.py:362`
- `src/cadrumo/domain/calculations/registry/_record_design.py:501`
- `dev/registry/_record_design_ir.py:73`
- `dev/registry/_record_design_ir.py:89`
- `dev/registry/_record_design_ir.py:172`
- `dev/registry/_export_tree.py:70`
- `dev/registry/_export_tree.py:227`
- `dev/registry/_export_tree.py:336`
- `dev/registry/_semantic_map.py:60`
- `dev/registry/_semantic_map.py:129`
- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:38`
- `.vault/audit/2026-08-10-aeat-export-fragment-generator-authority-s08-independent-review-audit.md:25`
- `dev/registry/tests/test_record_design_ir.py:22`
- `dev/registry/tests/test_export_tree.py:278`
- `dev/registry/tests/test_export_tree.py:305`
