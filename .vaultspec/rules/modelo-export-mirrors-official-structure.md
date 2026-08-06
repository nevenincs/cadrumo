---
name: modelo-export-mirrors-official-structure
---

# Modelo exports mirror the official structure

## Rule

Every modelo workbook export — offline xls and online Google Sheets alike — MUST
be generated from the single shared plan builder, render live spreadsheet
formulas with an explicit labelled start (input) and final (resultado) anchor,
and pass the registry-grounded parity gate (casilla set, numbering, section
order). A structural divergence from the official AEAT modelo layout is a hard
failure, never a warning.

The same registry-grounded completeness gate MUST bind the fixed-width
fichero-BOE (`.boe`) export, not only the workbook transport. `export_draft` MUST,
before it writes any bytes, assert that every casilla that is a calculation RESULT
(declares a formula) or is schema-required, and that the
`CalculationCompletenessManifest` lists AND the official record files (`manifest ∩
representable`, for the draft's disposition), carries a real value on disk; a blank
such casilla means the calculation did not populate it (a structurally-thin file
behind a valid SHA-256 digest) and MUST raise a hard `FilingExportError`
enumerating every missing casilla with its official number and segmento. Optional
operator-input casillas (retenciones, prior payments, deductions the taxpayer may
legitimately not have — e.g. Modelo 131 casillas 02/08/09/12/14) are NOT required
to carry a value: a blank slot is a valid zero, excluded from the required set. The
rendered set keys on value presence (`ModeloValue.value is not None`), never on
casilla-id membership, because `build_draft` emits an `EMPTY` (`value=None`) row for
every declared casilla. The gate is scoped to `format == "fixed_width"`; an
`xml_dictionary` export omits an absent casilla as a legitimately-absent optional
element, so the blank-slot thinness does not apply.

## Why

Per `2026-06-03-modelo-export-workbook-parity-adr` (research finding A), the
calc-sheets plan mirrored registry structure but wrote no formatting, marked no
start/final, and had no parity gate, so an operator could not see input→result flow
and nothing caught structural drift. Presentation is now typed plan facets defined
once in the builder and materialised identically by both transports, and "official
parity" is checked against the same registry authority the engine uses
(`CasillaDefinition.number`/`segmento`/`section`, the
`CalculationCompletenessManifest`) — not a separate hand-maintained spec.

## How

- **Good:** `build_export_plan(snapshot)` emits one `SheetExportPlan` (value/formula
  cells, number formats, section headers, start/final anchors, protected ranges,
  evidence); `build_offline_workbook` (openpyxl) and `apply_export_plan` (Sheets API)
  are two transports of that one plan, asserted to render the same content; the
  parity gate asserts casilla set = completeness-manifest required set (numbering +
  segmento), registry-declaration section order, and a live formula on every computed
  casilla — a divergence is a hard CI failure.
- **Good:** `assert_export_mirrors_manifest` runs inside `export_draft` after the
  rendered set is known (filtering `v.value is not None`) and before
  `output_path.write_bytes`; a fixed-width `.boe` omitting a required, representable
  casilla panics with an enumerated `FilingExportError` and no file is written.
- **Bad:** computing the rendered set from `{v.casilla_id for v in draft.values}`
  (id membership) instead of `v.value is not None` — every `EMPTY` casilla counts as
  rendered and the gate never fires on the real thin draft; or writing a thin `.boe`
  because the digest is valid (the digest is a byte-integrity lock, not completeness).
- **Bad:** writing formatting/start/final/evidence in one transport but not the
  other, asserting parity against a separate hand-maintained spec, or downgrading a
  structural divergence to a warning.

## Source

ADR `2026-06-03-modelo-export-workbook-parity-adr`; fichero-BOE binding ADR
`2026-07-01-fichero-boe-parity-gate-adr`. Enforced by `test_export_completeness_gate.py`,
`test_export_completeness_sets.py`, `test_fichero_boe_completeness_parity.py`.
