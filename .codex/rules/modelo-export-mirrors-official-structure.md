---
name: modelo-export-mirrors-official-structure
trigger: always_on
---

# Modelo exports mirror the official structure

## Rule

Every modelo workbook export — offline xls and online Google Sheets alike — MUST
be generated from the single shared plan builder, render live spreadsheet
formulas with an explicit labelled start (input) and final (resultado) anchor,
and pass the registry-grounded parity gate on casilla set and numbering. A
structural divergence from the official AEAT modelo layout is a hard failure,
never a warning.

The same registry-grounded completeness gate MUST bind the fixed-width
fichero-BOE (`.boe`) export, not only the workbook transport. `export_draft`
MUST, before writing any bytes, assert that every casilla that is a calculation
RESULT (declares a formula) or is schema-required, and that the
`CalculationCompletenessManifest` lists AND the official record files
(`manifest ∩ representable`, for the draft's disposition), carries a real value
on disk. A blank such casilla means the calculation did not populate it — a
structurally thin file behind a valid SHA-256 digest — and MUST raise a hard
`FilingExportError` enumerating every missing casilla with its official number
and segmento.

Optional operator-input casillas (retenciones, prior payments, deductions the
taxpayer may legitimately not have) are NOT required to carry a value: a blank
slot is a valid zero, excluded from the required set. The rendered set keys on
**value presence** (`ModeloValue.value is not None`), never on casilla-id
membership, because `build_draft` emits an `EMPTY` row for every declared
casilla. The gate is scoped to `format == "fixed_width"`; an `xml_dictionary`
export omits an absent casilla as a legitimately absent optional element.

**Casilla section order is deliberately not gated.** Section is presentation —
the plan emits section headers for a human reading the workbook — while what
must mirror the official modelo is the casilla SET and its numbering, both of
which are gated. Do not assert section order and do not rely on it.

## Why

The calc-sheets plan mirrored registry structure but wrote no formatting, marked
no start or final anchor, and had no parity gate, so an operator could not see
the input-to-result flow and nothing caught structural drift. Presentation is
now typed plan facets defined once in the builder and materialised identically
by both transports, and official parity is checked against the same registry
authority the engine uses — not a separate hand-maintained spec.

## How

- **Good:** `build_export_plan(snapshot)` emits one `SheetExportPlan` (value and
  formula cells, number formats, section headers, start/final anchors, protected
  ranges, evidence); the offline workbook builder and the Sheets applier are two
  transports of that one plan, asserted to render the same content. The parity
  gate asserts casilla set equals the completeness-manifest required set, a
  number-format facet on every numeric casilla, and a live formula on every
  computed casilla.
- **Good:** `assert_export_mirrors_manifest` runs inside `export_draft` after the
  rendered set is known and before the file is written, so a fixed-width `.boe`
  omitting a required representable casilla raises with an enumerated error and
  no file is written.
- **Bad:** computing the rendered set from casilla-id membership instead of
  value presence — every `EMPTY` casilla then counts as rendered and the gate
  never fires on a real thin draft.
- **Bad:** writing a thin `.boe` because the digest is valid; the digest is a
  byte-integrity lock, not a completeness claim.
- **Bad:** writing formatting, anchors or evidence in one transport but not the
  other, or downgrading a structural divergence to a warning.

## Source

ADR `2026-06-03-modelo-export-workbook-parity-adr`; fichero-BOE binding ADR
`2026-07-01-fichero-boe-parity-gate-adr`. Enforced by
`test_export_completeness_gate.py`, `test_export_completeness_sets.py`,
`test_fichero_boe_completeness_parity.py`.
