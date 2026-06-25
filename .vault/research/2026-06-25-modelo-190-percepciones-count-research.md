---
tags:
  - '#research'
  - '#modelo-190-percepciones-count'
date: '2026-06-25'
modified: '2026-06-25'
related: []
---



# `modelo-190-percepciones-count` research: `Modelo 190 número de percepciones distinct-(perceptor,clave) count`

Audit `2026-06-21-eoy-final-calculation-audit` (#22) flagged the Modelo 190 annual
`decl.total-percepciones` box as a likely over-declaration of the same shape the
RET-1 perceptor-count fix (`2026-06-24-retenciones-perceptor-count-adr`,
M180/M193) corrects, and asked whether M190 belongs in that fix. This research
grounds the M190 figure against the bundled AEAT Diseño de Registros and finds it
is a DIFFERENT figure (percepciones, not perceptores) that the RET-1 distinct-NIF
source would mis-state — so it is its own fix, and the clave-bearing data already
exists.

## Findings

### The defect: M190 sums quarterly perceptor counts across 9 claves

`decl.total-percepciones` is computed by formula `modelo-190-total-percepciones`
= `add()` of NINE per-clave relations
(`modelo-190-rel-111-{trabajo,actividades,premios,ganancias}-{dinerario,especie}-percepciones-anual`
plus `derechos-imagen`), each `aggregation = { op = "sum" }` over `1T-4T` of
Modelo 111 box `01`. Modelo 111 box `01` is `semantic_role = "perceptor_count"`
(label "…número de perceptores"). So the box sums quarterly PERCEPTOR counts: a
perceptor present under one clave across multiple quarters is counted once per
quarter, while the annual declaration holds ONE record per (perceptor,
clave/subclave). It over-declares by the cross-quarter recurrence factor — the
same op=sum shape as the RET-1 M180/M193 defect.

### The figure is PERCEPCIONES (registros tipo 2), not distinct PERCEPTORES

Bundled authoritative Diseño
`corpus/aeat_official/disenos_registro/modelo_190/files/01-190-orden-eha-3127-2009-...-actualizada-por-orden-hac-1431-2025-...pdf`
(extracted .md), positions 136-144: "NÚMERO TOTAL DE PERCEPCIONES. Se consignará
el número total de percepciones … las claves o subclaves de percepción a que
correspondan. (**Número de registros de tipo 2**.)" Type-2 = "Registro de
perceptor"; a perceptor with income under several claves/subclaves files several
type-2 records. So the figure = count of DISTINCT (perceptor NIF, clave/subclave)
records ≥ distinct perceptor NIFs.

This is why M190 is NOT in RET-1's scope: the RET-1 source materialises
`RetencionesAggregation.total_perceptors = len({distinct perceptor_nif})`
(collapsing claves) — correct for M180/M193's "número de PERCEPTORES" box, but it
UNDER-counts M190's percepciones (a perceptor under two claves = 2 percepciones, 1
NIF). Re-stamping M190 onto the RET-1 distinct-NIF source would swap an
over-declaration for an under-declaration (`no-silent-under-declaration`).

### The clave-bearing producer ALREADY EXISTS (the load-bearing finding)

The data-model blocker the #28 spec anticipated (no clave axis on the per-perceptor
record) does NOT apply: the M190/M193 per-perceptor detail source is the WITHHOLDING
source, and `WithholdingObservation` already carries `perceptor_tax_id`, `clave`
(2-char AEAT clave code), `subclave`, `percibido_dinerario/especie`, and
`retencion_practicada`. The withholding bindings already group `per_perceptor_clave`
(`modelo-190-perceptor-row-clave` / `-subclave`). So the correct percepciones count
is the count of DISTINCT (perceptor_tax_id, clave, subclave) `WithholdingObservation`
rows — derivable from the EXISTING clave-bearing model with no new clave axis on
`RetencionObservation` and no `RetencionesAggregation.total_percepciones` field.

### The withholding source is DEFERRED, not enrolled

`"withholding"` is in `DEFERRED_SOURCE_KINDS` (`_source_mesh.py`: "M190/M193
per-perceptor detalle — no live source; defer-with-advisory (S27)"). So today the
withholding detail is advisory-only on the calc path and the box falls back to the
wrong op=sum relation. The fix must enrol a distinct-(perceptor,clave) count over
the withholding source in `merge_source_resolutions` — the same enrol-or-advise
pattern RET-1 P02 applied to `retenciones_aggregation` (`no-dormant-source-resolvers`).

### Sibling / scope

RET-1 (`2026-06-24-retenciones-perceptor-count-adr`, M180/M193, distinct-NIF
`total_perceptors`) is the PERCEPTORES sibling; this is the PERCEPCIONES
(perceptor-clave) counterpart. They share the enrol-a-distinct-count-over-a-typed-
source pattern but use different distinct keys (NIF vs NIF+clave) and different
sources (the dedicated retención store vs the existing withholding detail). M190
stays OUT of RET-1 P03.
