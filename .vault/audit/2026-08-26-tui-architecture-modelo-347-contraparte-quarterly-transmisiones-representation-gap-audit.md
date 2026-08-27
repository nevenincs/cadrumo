---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fe0c793d593c407425e8a219ad8c6a150dcd352f155f08a040b998421a717112'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `modelo 347 contraparte quarterly transmisiones representation gap`

## Scope

Discovered while reading modelo 347's diseño de registro for the deferred
contraparte per-row binding family (S294, build deferred to a properly-paced
pass -- see the sibling reference document on the M347 contraparte binding
inventory). Comparing the bundled diseño de registro's Tipo-2 declarado
record fields against `Modelo347ContraparteRow`'s declared fields, read-only,
no code changed.

## Findings

### modelo 347 contraparte quarterly transmisiones representation gap | high | the model has no field for a quarterly amount the diseño de registro declares

`Modelo347ContraparteRow` (`src/cadrumo/domain/modelos/_row_models.py:620-623`)
declares exactly `importe_Q1` through `importe_Q4` and nothing else per
quarter. The bundled diseño de registro
(`corpus/aeat_official/disenos_registro/modelo_347/files/01-347-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1431-2025-de-3-de-diciembre-332-kb.pdf.extracted.md`)
pairs each quarter's "IMPORTE DE LAS OPERACIONES" field with a separate
"IMPORTE PERCIBIDO POR TRANSMISIONES DE [...]" sub-field at an adjacent byte
position (for example, positions 136-151 for 1T operaciones at line 459,
paired with positions 152-167 for 1T percibido-por-transmisiones at line
495; the same pairing repeats for 2T/3T/4T). No field on
`Modelo347ContraparteRow` carries this second quarterly amount for any
quarter -- this is not a naming or mapping mismatch, it is an absence: there
is nowhere on the row to put that value even if an operator or a future
resolver produced it.

What is lost, if the omission is not legitimate: a counterparty relation
whose declarable figure for a quarter includes transmisiones de inmuebles
sujetas a IVA (or whatever the "percibido por transmisiones" sub-field
specifically covers -- not confirmed in this pass) would have that portion
of the amount silently absent from any declaration built from this row,
with no refusal and no advisory anywhere naming the gap. That is exactly the
shape `no-silent-under-declaration` exists to catch: a positive economic
fact the diseño names a specific field for, with no path from fact to
casilla and no signal that it was dropped.

**This is an open finding, not a ruling.** Two explanations are both
consistent with the evidence and neither is confirmed: (a) the omission is
legitimate because this sub-field is out of scope for what
`Modelo347ContraparteRow` is meant to model (for instance, if it belongs
exclusively to a different record type, such as the modelo 347 "registro de
inmueble" this codebase's export layout already declares separately for
real-estate-related declarations), or (b) it is a genuine gap in the row
model that predates and is independent of the per-row binding family this
Step deferred. Resolving which requires reading the diseño's field
descriptions past the position table (not done in this pass) and likely a
tax review of what the "percibido por transmisiones" sub-field legally
covers and which record it belongs to.

## Recommendations

Before building or wiring `Modelo347ContraparteRow` into any automated
resolver (the deferred S294 pieces), resolve whether the quarterly
transmisiones sub-field belongs on this row, on the sibling
"registro de inmueble" row/record, or is genuinely out of scope for both --
grounded in the diseño's own field descriptions and, if the model needs a
new field, RD 1065/2007 and the modelo 347 diseño de registro read as the
governing authority. This decision should land as its own ADR-level
ruling if it changes the row model's shape, since a shape change to a
detail-row model used by threshold validation and (once built) export
rendering has effects wider than this one Step.

### modelo 347 contraparte quarterly transmisiones representation gap | update | the legitimacy question is now resolved, grounded against the bundled law

Read RD 1065/2007 art. 34.1 in the bundled consolidated text
(`corpus/normatives/html/rd-1065-2007.html.extracted.md`, "Artículo 34.
Cumplimentación de la declaración anual de operaciones con terceras
personas"). Paragraph 1.i) states verbatim: "Se harán constar separadamente
de otras operaciones que, en su caso, se realicen entre las mismas partes,
las cantidades que se perciban en contraprestación por transmisiones de
inmuebles, efectuadas o que se deban efectuar, que constituyan entregas
sujetas en el Impuesto sobre el Valor Añadido." (amounts received as
consideration for real-estate transfers subject to IVA must be stated
SEPARATELY from other operations with the same counterparty). This is the
legal basis for the diseño's paired "IMPORTE PERCIBIDO POR TRANSMISIONES"
sub-field at each quarter.

This resolves explanation (a) from the finding above against the evidence:
the sub-field is not scoped exclusively to the sibling "registro de
inmueble" record -- art. 34.1.i) requires the separate declaration
specifically WITHIN the per-counterparty operations reporting this record
carries, keyed by the same counterparty and quarter as the main amount.
Explanation (b) -- a genuine gap in `Modelo347ContraparteRow` -- is now the
better-supported reading: the row model has no field to carry a legally
required, separately-declarable amount for any filer with real-estate
transfer consideration among their M347-reportable operations.

This is still not a ruling that a field must be added, only that the
omission is real and grounded rather than speculative. Whether and how to
add it (a new field per quarter, a separate typed observation, or something
else) is a row-model shape decision with the same wider-effects caveat the
original recommendation names, and belongs with whoever picks up the
deferred S294 build.
