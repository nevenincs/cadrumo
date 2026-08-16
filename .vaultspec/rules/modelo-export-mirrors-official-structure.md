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

## A generated export tree is produced and checked by the generator's own authority

`dev/registry` owns the whole export-tree lifecycle, and every job in it has ONE
entry point. `validate_generated_export_tree` is the pre-cutover proof;
`publish_validated_generated_export_tree` validates, journals, swaps, verifies and
finalises under an exclusive lock with rollback; `check_generated_export_tree`
regenerates into an isolated candidate registry, validates that candidate through
the real loader and registry authority, then requires the published target to
attest to the same authorities with identical normalised loader semantics and
identical bytes.

Calling `render_complete_export_tree` straight into `src/`, or comparing committed
fragments with a directory diff, RE-IMPLEMENTS those and loses what they prove. A
byte comparison cannot ask whether a tree is a valid registry authority; it can
only say two directories differ. Modelo 210 and 232 were first generated that way,
so both were written without the pre-cutover proof, and a coverage refusal that
should have blocked publication surfaced later, at registry-load time.

Before building generator or export tooling, find the existing authority by MEANING
rather than reading one module and extending outward: record designs, semantic maps,
render profiles, provenance manifests, check mode and publication mode are one
pipeline, and its reach is not visible from any single file. The same applies to a
shape rule -- the parser and the development intermediate once held two copies of the
auxiliary-header contract and drifted into disagreeing about which modelos have one.

## How

- **Good:** a gate that drives `check_generated_export_tree` against the committed
  tree, so drift and invalid-authority both red through the one contract.
- **Bad:** rendering into the registry tree by hand, then asserting with `filecmp`;
  or a second copy of a shape rule kept "for independent validation".
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
