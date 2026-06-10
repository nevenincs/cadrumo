---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S04'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the Disenos de Registro workbook extractor (openpyxl) over the 74 xlsx plus 28 xls official AEAT files, materialising the casilla-number to field-position tables as schema-conformant text - the highest-value grounding surface (ADR D6)

## Scope

- `dev preprocessing tooling + src/aeat/_data/corpus/aeat_official/disenos_registro`

Implements the ADR D6 index-capability prerequisite for the highest-value
grounding surface: the Diseno de Registro field tables are the
casilla-number to field-position mapping a "what is field/casilla X" query
needs. Builds the production extractor against the interim sidecar contract
established earlier in this phase; the worked-example HTML stub stays a
worked example only.

## Description


- Ground the reader question via RAG + `rg`: confirm `openpyxl` 3.1.5 and
  `xlrd` 2.0.2 are both locked dependencies and both import; confirm `xlrd`
  2.x opens the legacy binary `.xls` BIFF format `openpyxl` cannot.
- Inventory the corpus: 74 `.xlsx` + 28 `.xls` across 30 modelo directories;
  inspect the field-table column layout (Nº, Posic., Lon, Tipo, Descripcion,
  Validacion, Contenido) and the modelo `manifest.json` artefact shape.
- Author the production extractor module `_workbook.py`: one
  `PreprocessUnit` per worksheet rendering the field table as pipe-delimited
  readable rows, `source_kind = DISENO_REGISTRO_WORKBOOK`, attribution
  pulled per-artefact from the modelo `manifest.json` (AEAT Sede source plus
  the official download URL).
- Add the openpyxl `.xlsx` reader and the xlrd `.xls` reader; normalise
  whole-number float cells (xlrd surfaces numbers as floats) so field
  numbers and positions read as ints.
- Add the byte-budget unit splitter so a hypothetical over-cap workbook
  splits into multiple sidecar parts rather than shipping an oversized,
  walker-skipped `.md`.
- Author a real-behaviour test suite (8 tests) over one real `.xlsx` and one
  real `.xls`, asserting schema validity, field-table content, walker
  pickup against the installed package, the 10 MB cap, the splitter, and an
  anti-tautology tampered-sidecar rejection.
- Run the extractor over all 102 workbooks, writing committed
  `*.extracted.md` + `*.extracted.json` sidecars in place.
- Verify: ruff check + format clean, `ty check` clean, the suite green, the
  subtree collect-only clean.

## Outcome

### Coverage: all 102 workbooks, both formats handled

- **74 `.xlsx`** read via `openpyxl` (`read_only`, `data_only`).
- **28 `.xls`** read via `xlrd` 2.0.2 - the legacy binary BIFF format
  `openpyxl` cannot open. No coordinator decision was needed: `xlrd` is
  already a locked project dependency (`xlrd>=2.0.1,<3` plus `types-xlrd`),
  so the 28 legacy designs are covered now, not deferred. `xlrd` 2.x dropped
  `.xlsx` support but retains `.xls`, which is exactly the split here
  (openpyxl for `.xlsx`, xlrd for `.xls`).
- All 102 extracted with zero failures. 102 `.md` + 102 `.json` sidecars
  written (one pair per workbook; no splits triggered).

### Largest sidecar vs the 10 MB cap

The largest rendered `.md` is **1.065 MB** (Modelo 200, 2025 design - an
~11 MB binary `.xls` whose field table is small; the binary bulk is
formatting, not table text). Every sidecar is comfortably under the walker's
10 MB `_MAX_FILE_SIZE`, so the byte-budget splitter (threshold 8 MB) never
fired on the real corpus. The splitter remains implemented and tested as the
safety net for any future larger design.

### The extractor

`_workbook.py` exposes `extract_workbook(source, *, repo_root)` (reads,
builds, writes the sidecar pair(s)) and `build_outputs(...)` (the pure
extract-to-records step). One `PreprocessUnit` per worksheet, titled by the
sheet name (e.g. `DP30300`), rendering each non-empty row as
`cell | cell | ...`. Trailing empty cells are trimmed; fully-empty spacer
rows are dropped. `WORKBOOK_EXTRACTOR_ID = "diseno-registro-workbook"`,
version `1.0`. Attribution is resolved from the modelo `manifest.json` by
matching the artefact whose `stored_path` ends with the source filename and
appending its official AEAT download URL; a standing AEAT Sede attribution
is the fallback so corpus text never ships unattributed (the BOE/AEAT
reuse-with-attribution obligation).

### Sample casilla-to-field table reads correctly

The Modelo 303 sheet `DP30300` renders the header
`Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido` followed
by the numbered field rows, e.g. `2 | 3 | 3 | An | Modelo |  | "303"` (field
2 at byte position 3, length 3, the Modelo constant "303") and
`5 | 11 | 2 | An | Período. (PP) |  | "01"..."12" o "1T"…"4T"`. Accented
Spanish (Descripción, Período, Añadido) renders correctly; the source cell
bytes are valid UTF-8 (an apparent mojibake in console output was terminal
display only). Field numbers normalise from xlrd floats to ints (no `2.0`
field rows).

### Verification

- Test: `test_workbook_extractor.py` - 8 tests, all green
  (`test_xlsx_extracts_field_position_table`, `test_xls_extracts_via_xlrd`,
  `test_sidecar_round_trips_and_is_walker_indexable`,
  `test_largest_corpus_sidecar_under_walker_cap`,
  `test_tampered_sidecar_is_rejected`,
  `test_budget_splitter_groups_oversized_units`,
  `test_render_sheet_normalises_and_drops_empty_rows`,
  `test_worked_example_workbooks_exist`). The full preprocess suite is 14
  green (8 here + 6 from the contract suite). `ruff check`, `ruff format
  --check`, `ty check`, and the subtree collect-only all clean.
- Sidecar paths verified not gitignored (`git check-ignore` exit 1 for both
  `.extracted.md` and `.extracted.json`), so the committed sidecars need no
  `.gitignore` change. The source workbooks stay tracked as before; the
  derived text sidecars are the committed, reviewable build inputs.

## Notes

- The `.xls` disposition is HANDLED, not flagged: `xlrd` was already locked,
  so no add/convert/defer coordinator decision was required. All 28 legacy
  `.xls` extract.
- openpyxl emits benign `UserWarning`s (print-area defined-name and
  header/footer parse) on some workbooks; they do not block extraction and
  are suppressed only at the bulk-run command level, not in the library
  code.
- No PM wave/phase/step tokens in production code or comments (the S02
  source-hygiene lesson applied; ADR decision ids appear only in this exec
  record).
- The committed sidecar tree retires when the upstream `vaultspec-rag`
  preprocess-hook lands (the established retirement trigger): the extractor
  re-targets the upstream sink and the `*.extracted.{md,json}` tree is
  deleted in one commit. `PreprocessOutput` precursor-compatibility is
  intact, so the migration is mechanical.
