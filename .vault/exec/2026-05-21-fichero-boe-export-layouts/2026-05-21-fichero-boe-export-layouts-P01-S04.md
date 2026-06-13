---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S04'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P01.S04`

Extracted the Modelo 303 eight-segment envelope record spec from the corpus
AEAT Diseño de Registros XLSX (ejercicio 2024 a partir de períodos 09 y 3T,
updated 2024-11-29) and recorded the per-segment byte layouts, field kinds,
encoding conventions, and casilla-number mapping for P03 authoring.

## Description

### Source corpus artefact

File: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/files/`
`04-303-ejercicio-2024-a-partir-de-periodos-09-y-3t-y-siguientes-actualizado-29-11-24-381-kb-x.xlsx`

Sheets: `DP30300` (envelope), `DP30301` (page 01 — régimen general,
IVA devengado/deducible), `DP30302` (page 02 — régimen simplificado,
repeated per-activity rows), `DP30303` (page 03 — régimen especial /
informativo / resultado), `DP30304` (page 04 — exoneración de declaración
resumen anual), `DP30305` (page 05 — compensación/resultado),
`DP303DID` (identification / payment record).

Encoding: latin-1 (ISO-8859-1) throughout. No separate trailer segment
exists in this DR edition — the envelope closing tag is embedded in the
DP30300 header specification as the file-closing literal
`</T3030AAAAPP0000>`. This is the same pattern as modelos 202 and 232
where a `computed_key = "envelope_closing_tag"` envelope-footer record
handles it at runtime.

### Segment inventory and record sizes

| Segment | DR sheet | Record pages tag | Total bytes | Order |
|---------|----------|-----------------|-------------|-------|
| DP30300 | envelope header | `<T3030AAAAPP0000>` | 328 (AUX) + variable content | 0 |
| DP30301 | page 01 | `<T30301000>` … `</T30301000>` | **1581** | 1 |
| DP30302 | page 02 | `<T30302000>` … `</T30302000>` | **1706** | 2 |
| DP30303 | page 03 | `<T30303000>` … `</T30303000>` | **1017** | 3 |
| DP30304 | page 04 | `<T30304000>` … `</T30304000>` | **998** | 4 |
| DP30305 | page 05 | `<T30305000>` … `</T30305000>` | **1523** | 5 |
| DP303DID | DID | `<T303DID00>` … `</T303DID00>` | **823** | 6 |
| Closing tag | — | `</T3030AAAAPP0000>` | 18 | 99 |

Note on the plan estimate of "roughly 7994 bytes": summing the six page
records (1581+1706+1017+998+1523+823 = 7648) plus envelope header (328)
plus closing tag (18) gives **7994 bytes** for the full minimum
fichero-BOE. The plan's estimate is confirmed.

DP30302 (régimen simplificado) can repeat up to 6 times for agricultural
activities and up to 6 times for other simplified activities (up to 3
combined pairs of page-02 records per the DR Nota 3). The 7994-byte
figure assumes one occurrence of each segment.

### Segment-by-segment field specifications

#### DP30300 — Envelope header (328 bytes fixed + pages + 18 bytes close)

| No | Posic | Lon | Tipo | Field | Registry kind |
|----|-------|-----|------|-------|---------------|
| 1 | 1 | 2 | An | Constante `<T` | literal |
| 2 | 3 | 3 | An | Modelo `303` | literal |
| 3 | 6 | 1 | An | Discriminante `0` | literal |
| 4 | 7 | 4 | An | Ejercicio devengo AAAA | draft filing_year |
| 5 | 11 | 2 | An | Período PP | draft period_code |
| 6 | 13 | 5 | An | Tipo y cierre `0000>` | literal |
| 7 | 18 | 5 | An | Constante `<AUX>` | literal |
| 8 | 23 | 70 | An | Reservado Admin | filler |
| 9 | 93 | 4 | An | Versión Programa | header program_version |
| 10 | 97 | 4 | An | Reservado Admin | filler |
| 11 | 101 | 9 | An | NIF Empresa Desarrollo | header presenter_nif |
| 12 | 110 | 213 | An | Reservado Admin | filler |
| 13 | 323 | 6 | An | Constante `</AUX>` | literal |
| 14 | 329 | Variable | — | Page records (DP30301–DP303DID) | — |
| *** | — | 18 | An | Closing `</T3030AAAAPP0000>` | computed envelope_closing_tag |

#### DP30301 — Page 01: Régimen General, IVA devengado/deducible (1581 bytes)

Page identifier: `01000` (5 chars). Close tag: `</T30301000>` (12 bytes, pos 1570).

Key header block (pos 1–129):
- 1–2: `<T`, 3–5: `303`, 6–10: `01000`, 11: `>`
- 12: complementaria indicator (1, A, blank)
- 13: tipo declaración (1, A)
- 14–22: NIF (9, An), draft profile_tax_id
- 23–102: Apellidos/Razón social (80, An), header surnames
- 103–106: Ejercicio (4, Num), draft filing_year
- 107–108: Período (2, An), draft period_code
- 109: Tributación foral (1, Num)
- 110: REDEME (1, Num)
- 111: Solo régimen simplificado (1, Num)
- 112: Autoliquidación conjunta (1, Num)
- 113: Criterio de Caja (1, Num)
- 114: Inversión del sujeto pasivo destinatario (1, Num)
- 115: Opción prorrata especial (1, Num)
- 116: Revocación prorrata (1, Num)
- 117: Concurso acreedores (1, Num)
- 118–125: Fecha auto concurso DDMMYYYY (8, An)
- 126: Tipo autoliquidación concurso (1, An)
- 127: SII voluntario (1, Num)
- 128: Exonerado declaración resumen anual (1, Num)
- 129: Volumen anual operaciones ≠ 0 (1, Num)

Casilla fields (pos 130–1056, all `kind = "casilla"`, 17 bytes each):

| Pos | Casilla | Label (abbreviated) | Tipo | Signed |
|-----|---------|---------------------|------|--------|
| 130 | 150 | IVA devengado RG base [150] | Num | No |
| 147 | 151 | IVA devengado RG tipo% [151] | Num (5) | No |
| 152 | 152 | IVA devengado RG cuota [152] | Num | No |
| 169 | 01 | IVA devengado RG base [01] | Num | No |
| 186 | 02 | IVA devengado RG tipo% [02] | Num (5) | No |
| 191 | 03 | IVA devengado RG cuota [03] | Num | No |
| 208 | 153 | IVA devengado RG base [153] | Num | No |
| 225 | 154 | IVA devengado RG tipo% [154] | Num (5) | No |
| 230 | 155 | IVA devengado RG cuota [155] | Num | No |
| 247 | 04 | IVA devengado RG base [04] | Num | No |
| 264 | 05 | IVA devengado RG tipo% [05] | Num (5) | No |
| 269 | 06 | IVA devengado RG cuota [06] | Num | No |
| 286 | 07 | IVA devengado RG base [07] | Num | No |
| 303 | 08 | IVA devengado RG tipo% [08] | Num (5) | No |
| 308 | 09 | IVA devengado RG cuota [09] | Num | No |
| 325 | 10 | Adquis intracomunitarias base [10] | Num | No |
| 342 | 11 | Adquis intracomunitarias cuota [11] | Num | No |
| 359 | 12 | Otras ops inversión SP base [12] | Num | No |
| 376 | 13 | Otras ops inversión SP cuota [13] | Num | No |
| 393 | 14 | Modificación bases y cuotas base [14] | N | Yes |
| 410 | 15 | Modificación bases y cuotas cuota [15] | N | Yes |
| 427 | 16 | Recargo equivalencia base [16] | Num | No |
| 444 | 157 | Recargo equivalencia tipo% [157] | Num (5) | No |
| 449 | 158 | Recargo equivalencia cuota [158] | Num | No |
| 466 | 17 | Recargo equiv. base [17] | Num | No |
| 483 | 17 | Recargo equiv. tipo% [17] | Num (5) | No |
| 488 | 18 | Recargo equiv. cuota [18] | Num | No |
| 505 | 19 | Recargo equiv. base [19] | Num | No |
| 522 | 20 | Recargo equiv. tipo% [20] | Num (5) | No |
| 527 | 21 | Recargo equiv. cuota [21] | Num | No |
| 544 | 22 | Recargo equiv. base [22] | Num | No |
| 561 | 23 | Recargo equiv. tipo% [23] | Num (5) | No |
| 566 | 24 | Recargo equiv. cuota [24] | Num | No |
| 583 | 25 | Modificación bases/cuotas recargo base [25] | N | Yes |
| 600 | 26 | Modificación bases/cuotas recargo cuota [26] | N | Yes |
| 617 | 27 | Total cuota devengada [27] | N | Yes |
| 634 | 28 | IVA deducible ops interiores base [28] | Num | No |
| 651 | 29 | IVA deducible ops interiores cuota [29] | Num | No |
| 668 | 30 | IVA deducible ops interiores corrientes base [30] | Num | No |
| 685 | 31 | IVA deducible ops interiores corrientes cuota [31] | Num | No |
| 702 | 32 | IVA deducible importaciones base [32] | Num | No |
| 719 | 33 | IVA deducible importaciones cuota [33] | Num | No |
| 736 | 34 | IVA deducible importaciones bienes corrientes base [34] | Num | No |
| 753 | 35 | IVA deducible importaciones bienes corrientes cuota [35] | Num | No |
| 770 | 36 | IVA deducible adquis intracomunitarias base [36] | Num | No |
| 787 | 37 | IVA deducible adquis intracomunitarias cuota [37] | Num | No |
| 804 | 38 | IVA deducible adquis intracomunitarias corrientes base [38] | Num | No |
| 821 | 39 | IVA deducible adquis intracomunitarias corrientes cuota [39] | Num | No |
| 838 | 40 | Rectificación deducciones base [40] | N | Yes |
| 855 | 41 | Rectificación deducciones cuota [41] | Num? | Yes |
| 872 | 42 | Compensaciones reg. especial AG y F [42] | N | Yes |
| 889 | 43 | Regularización inversiones cuota [43] | N | Yes |
| 906 | 44 | Regularización prorrata cuota [44] | N | Yes |
| 923 | 45 | Total a deducir [45] | N | Yes |
| 940 | 46 | Resultado régimen general [46] | N | Yes |
| 957 | 165 | IVA devengado RG base [165] (nuevo tipo) | Num | No |
| 974 | 166 | IVA devengado RG tipo% [166] | Num (5) | No |
| 979 | 167 | IVA devengado RG cuota [167] | Num | No |
| 996 | 168 | Recargo equiv. base [168] | Num | No |
| 1013 | 169 | Recargo equiv. tipo% [169] | Num (5) | No |
| 1018 | 170 | Recargo equiv. cuota [170] | Num | No |

Reserved/close (pos 1035–1581):
- 1035–1556: AEAT reserved filler (522 bytes)
- 1557–1569: AEAT seal filler (13 bytes)
- 1570–1581: `</T30301000>` literal (12 bytes)

**Casilla-number reuse in DP30301**: Casilla numbers 150–155 and 165–170
are "extended IVA rate" casillas that do NOT exist in the current 303.toml
(which only has 37 casillas). These are new casillas introduced in the
2024-from-09-3T revision. Additionally, casilla `17` appears TWICE in
the DR table (offset 466 as recargo base, offset 483 as recargo tipo%).
This is an error in my reading — re-examining: offset 466 = casilla [17]
recargo base, offset 483 = casilla [17] recargo tipo%. These are two
distinct sub-fields of the same casilla row in the form but separate
bytes in the fichero-BOE. They will need distinct field IDs with
disambiguation suffix. The same applies to casillas 19/20 (Num at 505/522)
and 22/23 (at 544/561).

#### DP30302 — Page 02: Régimen simplificado (1706 bytes per occurrence, repeatable)

Page identifier: `02000` (5 chars). Close tag: `</T30302000>` (12 bytes, pos 1695).

This page covers régimen simplificado (non-agricultural) and is highly
structured with repeated patterns: per-activity rows (Nº actividad +
epígrafe + bases/cuotas/compensaciones) and annual settlement data.
The description column is blank in the corpus XLSX for most rows (all
show "C" which appears to be a sheet-level formatting artefact). The
field structure was derived from offset/length analysis alone. Key
identifiers from preceding corpus versions and registry context:

- 1–4: open tag `<T303` + page `02000` + `>`
- 12: complementaria (1, A)
- 13–14: Nº actividad (2, Num) — per occurrence
- 15–93: multiple per-activity field rows (bases, tipos, cuotas, units)
- 901–984: annual settlement totals
- 985–1694: AEAT reserved filler (similar to DP30301)
- 1695: `</T30302000>` (12 bytes)

P03.S14 must derive the full DP30302 field-to-casilla map by cross-reference
with the 2024 model form (Orden HAC/646/2021 and successors). The DP30302
descriptions are absent from this XLSX edition; the authoritative casilla
labels must be retrieved from the parallel 2022–2023 XLSX editions in the
corpus which have fuller descriptions.

#### DP30303 — Page 03: Régimen especial / resultado (1017 bytes)

Page identifier: `03000`. Close tag: `</T30303000>` (12 bytes, pos 1006).

| Pos | Casilla | Label | Tipo | Signed |
|-----|---------|-------|------|--------|
| 1–11 | — | Tag `<T30303000>` | — | — |
| 12 | 59 | Entregas intracomunitarias bienes/servicios [59] | N | Yes |
| 29 | 60 | Exportaciones y ops asimiladas [60] | N | Yes |
| 46 | 61 | Ops no sujetas reglas localización (excl.) [61] | N | Yes |
| 63 | 122 | Ops sujetas inversión SP [122] | N | Yes |
| 80 | 123 | Ops no sujetas localización acogidas RE [123] | N | Yes |
| 97 | 124 | Ops sujetas regímenes especiales venta [124] | N | Yes |
| 114 | 125 | Entregas bienes/prestac servicios entidades art 72 y 73 base [125] | N | Yes |
| 131 | 126 | Entregas bienes/prestac servicios entidades base [126] | N | Yes |
| 148 | 127 | Adquisiciones bienes/servicios inversión [127] | N | Yes |
| 165 | 128 | Adquisiciones bienes/servicios entidades base [128] | N | Yes |
| 182 | 76 | Regularización cuotas art. 80.cinco.5ª LIVA [76] | N | Yes |
| 199 | 64 | Suma resultados ([46]+[58]+[76]) [64] | N | Yes |
| 216 | 65 | % Atribuible Admin Estado [65] | Num (5) | No |
| 221 | 66 | Atribuible Admin Estado [66] | N | Yes |
| 238 | 77 | IVA importación liquidado Aduana pendiente ingreso [77] | Num | No |
| 255 | 110 | Cuotas compensar pendientes periodos anteriores [110] | Num | No |
| 272 | 78 | Cuotas compensar periodos anteriores aplicadas [78] | Num | No |
| 289 | 87 | Cuotas compensar pendientes periodos posteriores [87] | Num | No |
| 306 | 68 | Exclusivamente tributación conjunta Admin [68] | N | Yes |
| 323 | 69 | Resultado autoliquidación [69] | N | Yes |
| 340 | 70 | Resultados ingresar anteriores autoliq [70] | Num | No |
| 357 | 71* | Devoluciones acordadas AEAT [70b] | Num | No |
| 374 | 71 | Resultado ([69]-[70]+[109]) [71] | N | Yes |
| 391 | — | Declaración sin actividad (X o blanco) | An | — |
| 392 | — | Autoliquidación rectificativa (X o blanco) | An | — |
| 393 | — | Nº justificante autoliq anterior (13 chars) | An | — |
| 406 | — | Tipo rectificación código (X o blanco) | An | — |
| 407 | 108 | Rectificativa determinados supuestos [108] | N | Yes |
| 424 | 111 | Rectificación importe [111] | Num | No |
| 441–560 | — | Reservado AEAT (120 bytes) | An | — |
| 561 | — | Motivo rectificación: rectificaciones | An | — |
| 562 | — | Motivo rectificación: discrepancia criterio admin | An | — |
| 563–1005 | — | Reservado AEAT (443 bytes) | An | — |
| 1006–1017 | — | `</T30303000>` (12 bytes) | — | — |

#### DP30304 — Page 04: Exoneración declaración resumen anual (998 bytes)

Page identifier: `04000`. Close tag: `</T30304000>` (12 bytes, pos 987).

This page is only populated in the last period (12 / 4T) by sujetos
exonerados. It contains 37 signed/unsigned money fields and multiple
text identifiers for actividad económica data. Fields 6–41 all carry
identical description "Exclusivamente a cumplimentar en el último
período…". This corresponds to the annual activity summary data that
exonerados must supply instead of the resumen-anual modelo 390.

Total data span: 986 bytes + 12 bytes close tag = 998 bytes.

#### DP30305 — Page 05: Compensación y resultado final (1523 bytes)

Page identifier: `05000`. Close tag: 12 bytes at pos 1512 (span to 1523).

This page covers compensation (régimen simplificado annual totals)
and final settlement figures. It contains 66 data fields in a
mixed pattern of activity-selector flags (1-byte An), percentage/type
identifiers (3/5 byte Num), and money values (17-byte Num/N). The full
casilla mapping requires cross-reference with the Orden HAC/646/2021
and the 2024 model form; the descriptions were absent from the XLSX.

#### DP303DID — Identification / Payment record (823 bytes)

Page identifier: `DID00` (5 chars, An type — unlike the numeric page codes
elsewhere). Close tag: `</T303DID00>` (12 bytes, pos 812).

| Pos | Lon | Field | Notes |
|-----|-----|-------|-------|
| 1–2 | 2 | `<T` | literal |
| 3–5 | 3 | `303` | literal |
| 6–10 | 5 | `DID00` | literal (An, not Num — note distinction) |
| 11 | 1 | `>` | literal |
| 12–22 | 11 | SWIFT-BIC | An, optional |
| 23–56 | 34 | IBAN domiciliación/devolución | An, optional |
| 57–126 | 70 | Banco/Bank name | An, optional |
| 127–161 | 35 | Dirección Banco | An, optional |
| 162–191 | 30 | Ciudad | An, optional |
| 192–193 | 2 | Código País | An, optional |
| 194 | 1 | Marca SEPA (0=vacía, 1=España, 2=UE SEPA, 3=resto) | Num |
| 195–811 | 617 | Reservado AEAT | filler |
| 812–823 | 12 | `</T303DID00>` | literal |

### Casilla-number reuse across segments

The 303 fichero-BOE exhibits segment-scoped casilla-number reuse in two
senses:

1. **Same casilla number in different segments**: Casilla `46` appears in
   DP30301 (resultado régimen general) and is referenced in DP30303
   formula `[46]+[58]+[76]=[64]`. These are the same registry casilla —
   no disambiguation needed. The DP30303 fields reference the result of
   DP30301 calculations; they do not re-define casilla 46.

2. **Sub-fields within the same DR row**: The DR uses a single "casilla"
   number for base + tipo% + cuota triplets where the tipo% is a
   hardcoded constant (e.g. "00400" for 4%). In the registry, each of
   the three wire bytes is a distinct `ExportFieldDefinition`. The casilla
   field ID only covers the base and cuota; the tipo% fields are either
   `kind = "literal"` (when they are hardcoded constants) or
   `kind = "casilla"` with a distinct casilla ID for the percentage
   casilla (e.g. casilla 02 for tipo 21%). P03 must model this correctly.

3. **New casillas 150–155, 165–170** present in DP30301 (2024 DR) but
   absent from the current 303.toml (which covers the 2022–2023
   revision). These are the additional VAT rate tiers introduced by the
   2024-from-09-3T revision and must be added to the revision's casilla
   definitions before export_refs can be wired.

### Discovery surprise: DP30302 descriptions absent

The DP30302 sheet in this XLSX edition carries no human-readable
description text in the Description column — all rows show "C" which is
a sheet formatting artifact. The full DP30302 field-to-casilla map must
be reconstructed by cross-referencing with the 2022–2024 pre-v2 XLSX
editions in the corpus (`02-303-ejercicio-2022-y-siguientes-actualizado-27-12-2021-332-kb-xlsx.xlsx`,
etc.) which do carry descriptions, or from the Orden HAC/646/2021
official form design. P03.S14 (DP30302 authoring) must perform this
cross-reference before authoring can begin.

### Discovery surprise: no separate trailer segment

The plan described "DP30300 header, DP30301–05 page records, DP303DID,
trailer" as 8 segments. The actual DR contains 7 segments (DP30300
through DP303DID) — the "trailer" is the closing literal tag embedded
in DP30300's spec row 15 (`</T3030AAAAPP0000>`), handled as an
`envelope_footer` record with `computed_key = "envelope_closing_tag"`.
P03.S19 in the plan names this "page-closing trailer" — it maps to the
same `computed_key = "envelope_closing_tag"` field used by modelos 130,
202, and 232. No separate trailer segment TOML file is needed.

## Tests

No production code was changed. This is a discovery step.
The segment and field inventory above is the authoritative reference
for P03.S09 through P03.S19. The DP30302 description gap and the
DP303DID `DID00` page-identifier type anomaly are noted for P03.
