---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e70fcedaedd8d659e828e2cf6812ac65ab4ac8d9bdd8929f757491a3346545c2'
related:
  - "[[2026-08-31-aeat-export-fragment-generator-authority-source-defect-adjudication-adr]]"
---

# `aeat-export-fragment-generator-authority` reference: `the M390 2022 page 7 close constant measured against its own declared slot`

Grounding for the modelo 390 filing-year 2022 record design, gathered while transcribing its semantic map. The measured object is the bundled hash-pinned workbook `corpus/aeat_official/disenos_registro/modelo_390/files/14-390-ejercicio-2022-actualizado-04-01-23-491-kb-xlsx.xlsx`, sha256 `7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe`, published by the Agencia Tributaria at `sede.agenciatributaria.gob.es`, declared in the registry as source ref `aeat-dr-390-2022` with `design_authority = authoritative`, `evidence_tier = layout_authority` and `review_status = reviewed`.

## Summary

The workbook closes each of its eight numbered pages with a record-tag constant. Seven of them agree with the slot the same cell declares. One does not, and the disagreement is internal to the published document.

### What was measured, and how

Two independent passes were run, because a single pass could not separate a defect in the source from a defect in the parser that reads it.

The first pass bypassed project code entirely: the workbook was opened as a zip archive and `xl/sharedStrings.xml` read directly. It contains, verbatim, `</T39001000>`, `</T39002000>`, `</T39003000>`, `</T39004000>`, `</T39005000>`, `</T39006000>`, `</T3900700>` and `</T39008000>`. The eleven-character string is present in the AEAT file itself, so no parser is implicated.

The second pass used the production reader rather than a hand-rolled one. Each cell was loaded through `load_record_design_intermediate` in `dev/registry/pipeline/_record_design_ir.py` and then put through the exact extraction path the export-tree gate applies in `dev/registry/pipeline/_export_tree.py` -- `_split_official_note_references`, the `_OFFICIAL_QUOTE_FOLD` translation and `_OFFICIAL_LITERAL_RE` -- and the extracted literal compared against the `length` the same field declares.

An earlier hand-written version of this check compared the raw cell text against the slot width and reported all eight pages as broken. That reading was an artifact: `content` carries the whole cell, `Constante "</T39001000>"` wrapper included, which the production regex strips. The measurement below is the one taken with the production parser.

### The measurement

| Page | Cell | Extracted literal | Length | Declared slot |
|---|---|---|---|---|
| 1 | A79 | `</T39001000>` | 12 | 12 |
| 2 | A97 | `</T39002000>` | 12 | 12 |
| 3 | A102 | `</T39003000>` | 12 | 12 |
| 4 | A24 | `</T39004000>` | 12 | 12 |
| 5 | A102 | `</T39005000>` | 12 | 12 |
| 6 | A54 | `</T39006000>` | 12 | 12 |
| 7 | A53 | `</T3900700>` | **11** | **12** |
| 8 | A66 | `</T39008000>` | 12 | 12 |

### Why this is a self-contradiction rather than a transcription choice

Cell A53 states two facts that cannot both hold: the constant it prints is eleven characters, and the slot it declares for that constant is twelve bytes. Any consumer must contradict one half of the cell to use the other.

Three independent signals agree on which half is wrong. The seven sibling pages all follow the pattern `</T3900N000>` where `N` is the page number, and only `</T39007000>` continues it. That value is also the only one consistent with the twelve-byte slot A53 itself declares. And it is the value the reviewed committed export layout already carries.

The defective reading is additionally unusable, not merely disfavoured. Adopting the eleven-character constant verbatim cannot produce a loadable tree: the literal-field builder compares bytes first and then immediately checks length, so an eleven-byte literal in a twelve-byte slot is refused by the following guard regardless of how the byte comparison is settled.

### Where the refusal is raised, and where it is not

The refusal surfaces as `RegistryValidationError: literal field 'modelo-390-page-07-close' value does not agree byte-for-byte with the exact official constant content`, raised in `dev/registry/pipeline/_export_tree.py`.

That module has no anomaly or exception hook of any kind. The similarly-named `anomaly_exceptions` parameter belongs to a different validator, `validate_semantic_map` in `dev/registry/pipeline/_semantic_map_validation.py`, whose own docstring records that such entries are documentary and that validation "never consults them to waive source, reference, or bijection validation". It cannot resolve this refusal and was never intended to.

The semantic map itself is not implicated: `validate_semantic_map` passes all 537 entries, because the map is internally consistent with the committed layout. Only the byte comparison against the pinned design can reach an error in the source document, which is what it did here.
