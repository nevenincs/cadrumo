---
name: modelo-export-mirrors-official-structure
trigger: always_on
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
representable`, for the draft's disposition), carries a real value on disk; such a
casilla rendered blank means the calculation did not populate it — a
structurally-thin file behind a valid SHA-256 digest — and MUST raise a hard
`FilingExportError` that enumerates every missing casilla with its official number
and segmento. Optional operator-input casillas (retenciones, prior payments,
deductions the taxpayer may legitimately not have — e.g. Modelo 131 casillas
02/08/09/12/14) are NOT required to carry a value: a blank slot is a valid zero,
not a thin file, so they are excluded from the required set. The rendered set keys
on value presence (`ModeloValue.value is not None`), never on casilla-id
membership, because `build_draft` emits an `EMPTY` (`value=None`) row for every
declared casilla. The gate is scoped to `format == "fixed_width"`; an
`xml_dictionary` export omits an absent casilla as a legitimately-absent optional
element, so the blank-slot thinness does not apply.

## Why

The `modelo-export-workbook-parity` research (finding A) found the calc-sheets
plan already mirrored registry structure and emitted live formulas but wrote no
formatting, marked no explicit start/final, and had no parity gate — so an
operator reviewing a filing artefact before submitting it outside the
application could not see input→result flow and nothing caught structural drift
from the official layout. The `2026-06-03-modelo-export-workbook-parity-adr`
decided presentation is typed plan facets (number formats, section headers,
start/final anchors, the `Evidencia` surface) defined once in the builder and
materialised identically by both transports, and that "official parity" is
checked against the same registry authority the calculation engine uses
(`CasillaDefinition.number`/`segmento`/`section`, the
`CalculationCompletenessManifest` projected from the AEAT Diseño de Registros) —
not a separate hand-maintained spec. This is the export-surface companion to
[[aeat-registry-authority-flow]] (the registry is the authority) and
[[ledger-derived-revisions-bundle-evidence]] (the evidence the workbook renders).

## How

- **Good:** `build_export_plan(snapshot)` emits one `SheetExportPlan` carrying
  value/formula cells, number formats, section headers, start/final anchors,
  protected ranges, and evidence; `build_offline_workbook` (openpyxl) and
  `apply_export_plan` (Sheets API) are two transports of that one plan, and a
  conformance test asserts they render the same content.
- **Good:** the parity gate asserts the exported casilla set equals the
  completeness-manifest required set (numbering + segmento), section ordering
  follows the registry declaration order, every computed casilla carries a live
  formula, and the start/final anchors are present and correctly placed; a
  divergence is a hard CI failure.
- **Good:** the gate reports coverage honestly — a modelo whose completeness
  manifest is incomplete yields a weaker gate that says so, rather than implying
  full parity.
- **Good:** `assert_export_mirrors_manifest` runs inside `export_draft` after the
  rendered set is known and before `output_path.write_bytes`; a fixed-width `.boe`
  that would omit a required, representable casilla panics with an enumerated
  `FilingExportError` naming each casilla's number and segmento, and no file is
  written.
- **Bad:** computing the rendered set from `{v.casilla_id for v in draft.values}`
  (id membership) instead of filtering `v.value is not None` — every declared
  casilla, including the `EMPTY` ones, then counts as rendered and the gate never
  fires on the real thin draft.
- **Bad:** letting a fixed-width `.boe` export write a structurally-thin file (a
  required casilla rendered blank) because the digest is valid — the digest is a
  byte-integrity lock, not a completeness signal.
- **Bad:** writing formatting, start/final, or evidence in one transport but not
  the other, or computing them at apply time instead of in the plan — offline
  and online then drift.
- **Bad:** asserting official parity against a separate hand-maintained layout
  spec instead of the registry completeness manifest, introducing a second drift
  surface.
- **Bad:** downgrading a structural divergence to a warning; the official
  casilla set, numbering, and section order are a gate, not a hint.

## Source

ADR `2026-06-03-modelo-export-workbook-parity-adr` (accepted); research
`2026-06-03-modelo-export-workbook-parity-research`; plan
`2026-06-03-modelo-export-evidence-parity-plan` (W03/W04/W05). Promoted per the
[[vaultspec-codify]] discipline. The fichero-BOE transport binding was added by
ADR `2026-07-01-fichero-boe-parity-gate-adr` (accepted) after the gate completed a
full implement→review→fix→validate cycle: an independent code review found the
rendered set keyed on casilla-id membership rather than value presence (so the gate
never fired on the real `EMPTY` thin state), which was fixed and locked with a test
that reproduces the production state. Enforced by
`test_export_completeness_gate.py`, `test_export_completeness_sets.py`, and
`test_fichero_boe_completeness_parity.py`.
