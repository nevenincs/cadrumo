---
tags:
  - '#audit'
  - '#export-required-flag-default'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:76c56bd4ee5edcea9f2936776d7650c2519143517fc2819b4de278f7db53081b'
related: []
---

# `export-required-flag-default` audit: `Export field required-flag default exposure`

## Scope

An uncommitted change to `_render_absent_numeric` in
`src/cadrumo/domain/calculations/registry/_fixed_width_codec.py` converted an absent
optional numeric export slot from refusing the whole export into zero-filling it, gated
entirely on the registry export field's `required` boolean. A grounding finding raised
the concern that `required` is a default-false-shaped field while the BOE-published
Order `orden-hap-1732-2014` runs the opposite way: *"Todos los campos tendrán contenido,
a no ser que se especifique lo contrario en la descripción del campo."*

If a field carries `required = false` without a per-field exception in its own AEAT
description, the change would newly zero-fill a slot AEAT says must carry content, which
is silent under-declaration.

This audit enumerates every export field declaring `required = false` across the whole
registry, classifies each against the bundled AEAT diseño de registro that governs it,
and rules on whether the landed numeric change is safe. Nothing was fixed; the codec file
was not modified.

## Method

Enumeration was taken from the loaded registry authority, not from a directory listing.
That choice was load-bearing: a glob over `export_layouts/` directories misses Modelo 349
entirely, which declares its layout under an `export/` directory and carries 52 fields.
The snapshot load found 15 export layouts and 310 declared export fields where the glob
found 18 fragments across 6 modelos.

`ExportFieldDefinition.required` is declared `required: bool` with no default, so every
field stanza must state the flag explicitly. There is no omitted-declaration case and the
enumeration is complete by construction.

Grounding was read from the bundled diseños each field cites through its own
`source_refs`, at the field's own offset, cross-checked against the field's byte position.
Every offset in the registry matched its diseño row exactly. The BOE Order text was read
from the bundled consolidated corpus.

No regulatory amount or rate is compiled into this population: the fields are byte slots,
not encoded values. The live-BOE cross-check mandate for amounts and rates therefore has
no subject here, and none was performed.

## Findings

### premise-scope-is-per-document | high | The governing content-default sentence is scoped to the Modelo 347 and Modelo 180 diseños and is absent from every Modelo 131 and Modelo 145 diseño

The sentence is real, correctly quoted, and load-bearing where it applies. In the bundled
Order it appears exactly twice: once immediately before the Modelo 347 record designs and
once inside Anexo III immediately before `MODELO 180 TIPO DE REGISTRO 1`. In both places
it is followed by *"Si no lo tuvieran, los campos numéricos se rellenarán a ceros"*, which
confirms the reading that zero-fill is conditioned on the exception rather than a
free-standing rule.

It does not extend beyond those two designs. All eight bundled Modelo 131 diseños and the
Modelo 145 diseño contain no equivalent sentence. Those documents use the inverse
convention: a per-field `Validación` column carrying `Obligatorio`, applied to 11 to 21
fields per design. Under that convention AEAT states the obligation positively on the
field's own row and is silent where the field is not obligatory, which is the mirror image
of the Order's convention rather than a gap in it.

This matters because applying the Order's default to Modelo 131 and Modelo 145 would
import one document's convention into documents that declare their own, and would
manufacture a 74-field defect that the source text does not support. The premise was
verified rather than assumed, and the initial read that placed the sentence outside Modelo
180 was wrong and was corrected against Anexo III.

### wrong-population-is-empty | critical | No export field carries required = false without a per-field basis; the landed numeric change is safe as it stands

Of 310 declared export fields, 171 declare `required = false`. Of those, 76 are numeric
(62 money, 14 integer) and form the exact blast radius of the change; the remaining 95 are
text, boolean or filler and are not reachable by it. The 76 divide as 60 Modelo 131
casillas across four revisions, 14 Modelo 145 fields, and 2 Modelo 180 fields.

The three-way classification of the 76 is: 76 correct, 0 wrong, 0 undeterminable.

Two are correct on an explicit clause. Modelo 180 `EJERCICIO DEVENGO` at positions 110 to
113 reads *"Únicamente se cumplimentará este campo en los supuestos que a continuación se
indican, en caso contrario se rellanará a ceros"* — the strongest available form, stating
both the condition and the zero fill, in a design the content-default premise does govern.
This is the pattern the finding predicted, and its neighbour behaves as predicted too:
`NIF DEL REPRESENTANTE LEGAL` states *"En cualquier otro caso el contenido de este campo
se rellenará a espacios"* while `NIF DEL PERCEPTOR` states no exception and is authored
required.

Seventy-four are correct under the positive-marker convention of their own design. Every
Modelo 131 casilla 01 through 15 carries a blank `Validación` cell in all four revisions,
verified individually rather than sampled, with registry offsets matching diseño positions
exactly. Each is substantively conditional on a régimen section or an entitlement the
filer may not have: casillas 01 and 02 on non-agricultural módulos activity, 03 and 04 on
the distinct-activities section, 05 and 06 on agrícola, ganadera y forestal activity, 09 on
the article 110.3.c threshold the design states at fields 56 and 57, 12 on the vivienda
entitlement the design states at field 61, and 08, 11 and 14 on prior-period facts that may
not exist. The Modelo 145 fields are per-descendant and per-ascendant slots and two
conditional payment amounts, on a comunicación de datos al pagador that declares no tax.

The grounding for these 74 is weaker in kind than the two explicit clauses: it rests on
the design's convention plus substantive conditionality, not on a literal per-field *"o
blanco"* phrase. That distinction is recorded rather than smoothed over. It does not move
any field into the wrong band, because under each design's own stated convention the
absence of the marker is the per-field statement.

### completeness-gate-covers-24-of-76 | medium | Two thirds of the blast radius is a second gate away from the wire, and the export gate reads the draft rather than the rendered payload

The export completeness gate in `assert_export_mirrors_manifest` runs before
`atomic_write_bytes` and refuses when a casilla that declares a formula or is
schema-required, is listed in the completeness manifest, and is representable, carries no
value. Twenty-four of the 76 satisfy that predicate: Modelo 131 casillas 04, 06, 07, 10, 13
and 15 across four revisions, which includes `Total` and `Resultado de la declaración`.

The gate derives its rendered set from the draft through `value.value is not None`, not
from the emitted bytes, so a codec zero-fill cannot launder it. Those 24 still refuse, one
stage later than before, and no bytes reach disk. The comment on the gate already names
Modelo 131 casillas 02, 08, 09, 12 and 14 as deliberately excluded optional operator
inputs, so the two-tier split is an existing, documented design decision rather than an
accident this change created.

The residual 52, where the `required` flag is the only gate, are 36 Modelo 131 casillas
(01, 02, 03, 05, 08, 09, 11, 12, 14 across four revisions), the 14 Modelo 145 fields, and
the 2 Modelo 180 fields.

### behaviour-delta-confirmed-empirically | medium | The change was exercised against real registry fields rather than reasoned about

HEAD's path was reproduced exactly by calling `_require_allowed_value` and
`_render_typed_value` with an empty value, both unchanged by the working-tree diff, so the
contended codec file was never touched. On Modelo 131 casilla 08, Modelo 131 casilla 15 and
the Modelo 145 pensión compensatoria field, HEAD refuses with an invalid-numeric-value
error and the working tree renders seventeen zeros. The delta is exactly as described.

### required-flag-cannot-express-conditionality | medium | The flag is static while the AEAT obligations behind it are conditional, and four Modelo 131 casillas per revision sit on the under-declaring side of that gap

The obligations this audit cleared are conditional — fill if you carry that activity,
leave at zero otherwise — but `required` is a static per-field boolean that cannot
distinguish "no activity, so zero is the truth" from "has activity, but the value never
reached the draft". For the residual population the two cases render identically.

The direction matters. Zero-filling casillas 08, 09, 11, 12 and 14 understates a
deduction, which over-pays: wrong for the taxpayer, but not under-declaration. Zero-filling
casillas 01, 02, 03 and 05 understates income or base, which is the under-declaring
direction, at 16 fields across four revisions.

Three of those four are contained by the formula chain, which the gated casillas close
over: casilla 03 feeds 04, casilla 05 feeds 06, and casilla 02 feeds 07, and 04, 06 and 07
are all gated. Casilla 01, `Suma de rendimientos netos`, is the exception. It is
`input_kind = "manual"`, declares no formula, is not schema-required, and feeds no
formula, so nothing downstream notices its absence. A módulos filer whose casilla 01 never
reached the draft would export a record declaring zero rendimientos alongside a non-zero
pago fraccionado previo.

This is a gap in the app's guard coverage, not a mis-authored flag: AEAT's own design
permits zeros at that position, so the fix is not the right place to catch it. It belongs
in the verify and advisory layer that already exists for exactly this class of
positive-input-with-zero-dependent case.

### m145-has-no-completeness-manifest | medium | The second tier is absent for Modelo 145, so its 14 numeric fields have no gate but the flag

The completeness gate is invoked only when the revision carries a completeness manifest.
Modelo 145 carries none, so the gate is skipped entirely for it and all 14 of its numeric
`required = false` fields rest solely on the flag. This does not change their
classification — all 14 are correct against the diseño — but it removes the defence in
depth the other modelos have. Modelo 100 layouts are `xml_dictionary` and declare no
fields, and the gate is scoped to fixed-width regardless.

### m131-2025-omits-declaracion-complementaria | low | Incidental defect adjacent to the audited surface, not actioned

The Modelo 131 2025 revision declares no `Declaración complementaria` export field, while
the 2019-2023, 2024 and 2026 revisions each declare one and all three diseños, including
the 2025 diseño, carry the field at position 692 as *"blanco o X"*. This is a missing
field rather than a required-flag misdeclaration, so it is outside this audit's question
and was not investigated further or fixed. Reported as inventory to verify.

### enumerate-from-the-snapshot-not-the-tree | low | A directory glob undercounts the export-layout corpus by one whole modelo

Modelo 349 declares its export layout under an `export/` directory rather than
`export_layouts/`, and carries 52 fields of which 22 declare `required = false`. A glob
scoped to `export_layouts/` returns nothing for it. All 22 are `kind = "filler"`, which the
codec renders as blanks before any required check is consulted, so Modelo 349 contributes
nothing to the blast radius — but the corpus shape is the lesson, and the same glob would
have hidden a numeric population had one been there.

## Verdict on the landed change

Safe as it stands. The population the finding was looking for is empty: no export field
carries `required = false` without a basis in its own AEAT design, so there is no field the
change newly zero-fills where AEAT mandates content. The change's safety claim rests on
`required = false` meaning "AEAT permits this slot to be blank", and that meaning holds for
all 76 fields it can reach.

Two qualifications, neither of which argues for reverting. The premise the concern was
built on is narrower than assumed — it governs two designs, not the corpus — so the
concern's reasoning does not transfer to the 74 Modelo 131 and Modelo 145 fields even
though its conclusion for them happens to be the same. And casilla 01 of Modelo 131 is a
genuine, pre-existing hole in guard coverage that this change makes quieter by turning a
refusal into a zero; it did not create the hole, and closing it in the codec would break
the legitimate no-activity filer.

## Recommendations

Leave the numeric change as authored and do not re-author any `required` flag. The
registry matches its sources on every field this change can reach, and a sweep to
`required = true` would refuse exports that AEAT accepts.

Close the Modelo 131 casilla 01 gap in the verify layer rather than the export layer, as an
advisory that fires when módulos activity is declared and the suma de rendimientos netos
resolves to zero. This is the same shape as the existing positive-input-with-zero-dependent
guard and belongs beside it, not in the codec.

Decide whether a revision that declares fixed-width export fields must also declare a
completeness manifest, so the second tier cannot be silently absent as it is for Modelo
145. That is an architecturally significant choice about whether the two tiers are
independent or coupled, and it needs a decision record rather than a patch.

Record in the export field's own documentation that `required` means "the governing diseño
permits this slot to be blank", derived per design from either an explicit exception clause
or the absence of a positive obligation marker. The flag currently reads as though one
universal convention backs it, and this audit found two opposite conventions in force.

Verify and close the Modelo 131 2025 missing complementaria field separately.

## Caveats

The enumeration was captured from a snapshot load at a point in time. A concurrent peer
edit to the two Modelo 180 perceptor layout fragments landed during the audit; it adds
`allowed_values` only and changes zero `required`-flag lines, so the counts are unaffected.
That edit is mid-flight and currently leaves the registry unloadable pending its paired
`value_policy` declaration, which is the peer's to finish and was left untouched.

The bundled corpus was treated as preferred but not infallible, per standing practice. No
numeric amount or rate is encoded in this population, so the live-BOE cross-check that
would otherwise be mandatory had no subject.
