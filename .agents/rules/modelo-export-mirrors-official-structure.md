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
[[vaultspec-codify]] discipline.
