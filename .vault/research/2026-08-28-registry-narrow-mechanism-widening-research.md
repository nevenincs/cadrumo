---
tags:
  - '#research'
  - '#registry-narrow-mechanism-widening'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4d8fd695584e285eb6dc02dca22aeab7bdd115dcc3f87f935c2fbdb1da684ac0'
related: []
---

# `registry-narrow-mechanism-widening` research: `three registry mechanisms whose deliberate narrowness now blocks a measured defect`

Three unrelated registry mechanisms were each written narrow on purpose, each says so
in its own docstring, and each has now met a real defect it cannot express. Widening
any of them is a judgement about how much a safety mechanism may admit before it stops
being one, so the three are gathered here rather than adjudicated one at a time in
whichever loop tick tripped over them. The evidence below is measurement only; the
ruling belongs in the sibling ADR.

The shared shape matters more than the three instances. In every case the narrowness is
correct as written, the defect is real, and the cheap fix -- widen the matcher until the
red goes away -- would silently readmit the failure the narrowness exists to prevent. One
of the three was attempted that way during discovery and had to be reverted, which is the
strongest evidence in this document.

## Findings

### A mis-declared range START has no correction kind, and Modelo 165's 2013 orden needs one

`02-165-orden-hap-2455-2013.pdf` leaves wire positions 102-103 undescribed. Its
`Tipo 2 - Registro De Socios O Partícipes` sheet runs `97-101 PORCENTAJE DE
PARTICIPACIÓN` (subdivided `97-99 ENTERO`, `100-101 DECIMAL`) and then jumps to
`104-500 BLANCOS`. The extractor reads every row that is present; nothing describes the
two positions.

Both sibling editions of the same orden publish `102-500 BLANCOS`:
`01-165-diseno-de-registro-actualizado-en-2023.pdf` and
`03-165-orden-hap-2455-2013-actualizado-por-orden-hfp-1822-2016.pdf`. The three editions
are otherwise identical across the surrounding rows (`95-96 DÍA`, `97-101`, `97-99`,
`100-101`, `108-120 NÚMERO IDENTIFICATIVO`), and no edition describes a field at 102-103.
The two positions are therefore filler in every reading, and only the original
mis-declares where filler begins.

This is a corpus defect in an AUTHORITATIVE source, not a parser gap. The source is
`aeat-dr-165-2013-2015`, carrying `design_authority = "authoritative"` and cited by
revision `2013-2015`. That revision has `layouts=0` today, which is the only reason
nothing has bitten: if the era acquires an export layout the hole becomes a real
byte-coverage gap.

The three declared `RecordDesignCorrection` kinds address a data row read with a blank
type cell, a header cell, and one naturaleza-less single-position row. None expresses a
filler row whose declared START is wrong, and the schema states the narrow gate is
deliberate -- a single position with no naturaleza is otherwise indistinguishable from a
numbered prose sentence, and 41 bundled designs open a description with the field's own
range.

### The auxiliary-envelope recogniser admits only Modelo 390's shape, so Modelo 303 takes a fallback its own module calls wrong

`_auxiliary_envelope_header` returns a classification only for a sheet with no declared
total, a terminal extent of exactly 328, and exactly as many fields as
`RecordDesignAuxiliaryEnvelopeHeaderRole` has members. Its docstring is explicit that
this recognises "only the exact total-less Modelo 390 page-zero source shape".

Modelo 303's `DP30300` is envelope-shaped by its constants -- `<T` at 1, `<AUX>` at 18,
`</AUX>` at 323 -- but does not match that shape, so it is not classified as an auxiliary
header. It then fails to join any record: its only constant shared with any of the six
authored records is `(1,2) = '<T'`, which all six carry and all agree on, so
`_join_record` sees a six-way tie and correctly refuses to pick arbitrarily. Its siblings
all join cleanly on their discriminating `(6,5)` code (`DP30303` to `m303-resultados` via
`03000`, `DP30304` to `m303-exonerado-390` via `04000`, `DP303DID` to
`m303-domiciliacion` via `DID00`).

Unjoined and unclassified, `DP30300` falls to the generic coverage fallback -- the branch
the coverage module documents as "actively wrong" for a header, because neighbouring
records' fields sit at the same low offsets and a header position gets "covered" by an
unrelated record's field. Modelo 232 previously demonstrated exactly that, blaming
`dr23201` fields for writing into `DR23200`'s administración bytes.

This affects all five current Modelo 303 revisions: 2022, 2023, 2024-hasta-08-y-2t, 2025
and 2026-y-siguientes. The consequence is not a wrong number but an unproven one: the
coverage verdict for Spain's principal IVA return is currently produced by the weaker
any-record question rather than a real per-record join.

Two sheets ARE correctly classified and must stay excluded from any debt inventory:
Modelo 232's `DR23200` in both revisions. A first version of the join ratchet pinned them
as fallback debt, which overstated it -- an auxiliary header never reaches the fallback at
all.

### No BindingSourceKind supplies a constant, so Modelo 720 asks the taxpayer for AEAT's record format

Modelo 720's `tipo-de-registro` (@1, length 1) and `modelo-declaracion` (@2-4, length 3)
are declared `source = "manual_input"` on both the type_1 and type_2 records. The
application therefore prompts the operator for the record-type marker and the modelo
number. The prompt is answerable-blank, and a blank emits at those positions behind a
valid digest, producing a file AEAT cannot parse.

The bundled diseño states all four as constants in its own field-content text:
"Constante número '1'." and "Constante «720»." on the declarante record, "Constante '2'."
and "Constante '720'." on the detalle record.

A literal-field fix was attempted and fully reverted. It worked mechanically -- both
sheets joined and coverage reported zero complaints through the real per-record join --
but it violates a deliberate contract that three tests pin:
`test_m720_binding_derived_design_distinguishes_declared_binding_representation` asserts
every inline field satisfies `casilla_id is None and literal is None`, stating "M720 must
represent every casilla through a binding, never an inline export field", and the two
`test_committed_modelo_720_type_N_bindings_target_..._record` tests assert the binding set
itself opens at position 1. The tests are right; the edit was wrong.

The clean fix keeps the constants as bindings while removing the operator prompt, which
requires a constant-supplying source kind. Enumerating all 32 `BindingSourceKind` members
shows none qualifies: the only non-aggregation members are `manual_input` and `profile`.

### The defect and the join failure are one root cause, which is what makes the ratchet worth keeping

Modelo 184 shows the same shape independently. Its `tipo2.tipo-hoja` and
`tipo3.tipo-hoja` at position 76 carry `input_kind=manual`, `required=False`, no formula,
no binding and no constraints, while the diseño states `Constante "E".` for the rentas
record and `Constante "S".` for the socio record. A blank at 76 leaves the record type
indeterminate. Those same two records declare identical literals at `(1,1)` and `(2,3)`,
so their sheets tie and the join refuses -- the missing discriminator and the
blank-emission risk are the same fact seen twice.

This generalises: a record whose discriminating constant is routed through a data channel
has no literal for the join AND can emit blank. The export-layout join ratchet is
therefore a defect worklist, not checker noise.

Scope limit worth stating, because it corrects an earlier claim made during discovery: a
scan for unconditional constants on optional manual channels returned zero instances
outside Modelo 720, but that scan skipped sheets that do not join, so it could not have
seen Modelo 184. The zero held only over joined sheets. The remaining ratchet entries are
precisely the population it excluded.

### What a widening must not readmit

The candidate list is not the defect list, measured twice.

Scanning every modelo by the diseño's own content text finds 46 fields declaring a
"Constante", and most are correctly modelled. `filler` is right for Modelo 714's
"Constante. Blanco" and "Constante «blanco»", because the constant IS blank. Modelo 369's
`[blanco | constante "C"]` is genuinely conditional, so forcing a literal would hard-code
one branch of an either/or and corrupt the record. Only an UNCONDITIONAL constant on a
channel that can emit blank is a defect.

The same trap appeared in the row parser. Across all 102 bundled design PDFs, 183 rows
carry a bare-dash naturaleza; the obvious rule "no position range means prose" would have
dropped 8 legitimate single-position `BLANCOS` rows at 58, 81 and 500 across modelos 185,
270, 296 and 347. The discriminator that survives measurement is semantic: a dash
naturaleza describes its filler.

### Not investigated

Whether Modelo 303's `DP30300` should be classified as an auxiliary envelope header at
all, or is a third record shape needing its own classification, was not established --
only that it is not the Modelo 390 shape and that the fallback is wrong for it. The
328-byte extent that defines the current recogniser was not traced to a published AEAT
rule, so whether it is a general envelope property or a Modelo 390 particular is open.

Whether any operator has in practice supplied Modelo 720's constants (making today's
output correct despite the modelling) was not measured; no filed-output corpus was
consulted.

## Sources

- `src/cadrumo/domain/calculations/registry/record_design.py` -- `_parse_pdf_row`,
  `_auxiliary_envelope_header`, `_NARRATIVE_PDF_ROW_RE`
- `src/cadrumo/domain/calculations/registry/record_design_schema.py` --
  `RecordDesignFieldTypeCorrection`, `RecordDesignHeaderCellCorrection`,
  `RecordDesignSinglePositionCorrection`
- `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py` --
  `_join_record`, `_sheet_constants`, `_record_literals`, the auxiliary-header branch
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_720_registry.py`
- `src/cadrumo/domain/calculations/registry/tests/test_clasificacion_casillas_oficiales.py`
- `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py`
- `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings/0001-bindings.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_165/files/` -- the three
  editions compared
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_720/files/01-720-599-kb-pdf.pdf`
- `cadrumo.core.aggregation.BindingSourceKind` -- all 32 members enumerated
- Related decisions: `2026-06-26-binding-source-kind-taxonomy-unification-adr`,
  `2026-08-19-registry-export-layout-coverage-adr`
