# Modelo exports mirror the official structure

Every modelo workbook export — offline xls and online Sheets alike — MUST be
generated from the single shared plan builder, render live spreadsheet formulas
with an explicit labelled start (input) and final (resultado) anchor, and pass
the registry-grounded parity gate on casilla set and numbering. A structural
divergence from the official AEAT layout is a hard failure, never a warning.

The plan is typed presentation facets defined once in the builder and
materialised identically by both transports; parity is checked against the same
registry authority the engine uses, not a hand-maintained spec.

**Casilla section order is deliberately not gated.** Section is presentation; what
must mirror the official modelo is the casilla SET and its numbering, both of
which are gated. Do not assert section order and do not rely on it.

## The fixed-width export carries the same completeness gate

`export_draft` MUST, before writing any bytes, assert that every casilla that is
a calculation RESULT (declares a formula) or is schema-required, **and** that the
completeness manifest lists **and** the official record files can represent,
carries a real value on disk. A blank such casilla means the calculation did not
populate it — a structurally thin file behind a valid digest — and MUST raise a
hard `FilingExportError` enumerating every missing casilla with its official
number and segmento.

Optional operator-input casillas (retenciones, prior payments, deductions the
taxpayer may legitimately not have) are NOT required: a blank slot is a valid
zero, excluded from the required set.

**The rendered set keys on value presence (`v.value is not None`), never on
casilla-id membership**, because `build_draft` emits an EMPTY row for every
declared casilla. The gate is scoped to `format == "fixed_width"`; an
`xml_dictionary` export omits an absent casilla as a legitimately absent optional
element.

## How

- **Bad:** computing the rendered set from casilla-id membership — every EMPTY
  casilla then counts as rendered and the gate never fires on a real thin draft.
- **Bad:** writing a thin file because the digest is valid. The digest is a
  byte-integrity lock, not a completeness claim.
- **Bad:** writing formatting, anchors or evidence in one transport but not the
  other, or downgrading a structural divergence to a warning.

Source: ADRs `2026-06-03-modelo-export-workbook-parity-adr`,
`2026-07-01-fichero-boe-parity-gate-adr`. Gates:
`test_export_completeness_gate.py`, `test_export_completeness_sets.py`,
`test_fichero_boe_completeness_parity.py`.
