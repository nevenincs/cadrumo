---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S03'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P01.S03`

Extracted the Modelo 130 single fixed-width record spec from the corpus AEAT
Diseño de Registros XLS (ejercicios 2019 y siguientes, versión 1.2, Orden
HAP/258/2015) and cross-checked against the existing `export_layouts` block
in `src/aeat/_data/registry/aeat/modelos/130.toml`.

## Description

### Source corpus artefact

File: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_130/files/`
`01-130-orden-hap-258-2015-ejercicios-2019-y-siguientes-actualizado-marzo-2019-176-kb-xls.xlsx`

Sheets: `DR 13000` (envelope header), `DR 13001` (page-01 record).
The DR declares version 1.2 (Orden HAP/258/2015, updated March 2019).
Encoding: the DR notes explicitly state `An` fields are left-justified
space-padded, `Num` fields are right-justified zero-padded, `N` fields
(signed numeric) are right-justified zero-padded with `N` in position 1
for negative values. Encoding for the wire format: Windows-1252 / latin-1
(confirmed by the fichero-BOE export ADR section 4).

### DR 13000 — Envelope header (AUX block)

| No | Posic | Lon | Tipo | Description | Content |
|----|-------|-----|------|-------------|---------|
| 1 | 1 | 2 | An | Constante | `<T` |
| 2 | 3 | 3 | An | Modelo | `130` |
| 3 | 6 | 1 | An | Constante | `0` |
| 4 | 7 | 4 | An | Ejercicio devengo (AAAA) | — |
| 5 | 11 | 2 | An | Período (PP) | `1T`–`4T` |
| 6 | 13 | 5 | An | Constante | `0000>` |
| 7 | 18 | 5 | An | Constante | `<AUX>` |
| 8 | 23 | 70 | An | Reservado Admin | BLANCOS |
| 9 | 93 | 4 | An | Versión Programa (Nota 1) | — |
| 10 | 97 | 4 | An | Reservado Admin | BLANCOS |
| 11 | 101 | 9 | An | NIF Empresa Desarrollo (Nota 1) | — |
| 12 | 110 | 213 | An | Reservado Admin | BLANCOS |
| 13 | 323 | 6 | An | Constante | `</AUX>` |
| 14 | 329 | Variable | An | Contenido del fichero (page records) | — |
| 15 | *** | 18 | An | Constante closing tag | `</T1300AAAAPP0000>` |

Envelope header fixed portion: positions 1–328 (328 bytes). The `***`
closing tag is appended after all page records.

### DR 13001 — Page-01 record (600 bytes total)

| No | Posic | Lon | Tipo | Field | Notes |
|----|-------|-----|------|-------|-------|
| 1 | 1 | 2 | An | Open tag `<T` | literal |
| 2 | 3 | 3 | Num | Modelo `130` | literal |
| 3 | 6 | 2 | Num | Página `01` | literal |
| 4 | 8 | 4 | An | Close tag `000>` | literal |
| 5 | 12 | 1 | A | Indicador complementaria | blank or `X` |
| 6 | 13 | 1 | A | Tipo declaración | I/U/G/N/B (Nota 1) |
| 7 | 14 | 9 | An | NIF sujeto pasivo | draft profile_tax_id |
| 8 | 23 | 60 | An | Apellidos | header surnames |
| 9 | 83 | 20 | An | Nombre | header name |
| 10 | 103 | 4 | Num | Ejercicio devengo | draft filing_year |
| 11 | 107 | 2 | An | Período | draft period_code |
| 12 | 109 | 17 | Num | [01] Ingresos computables | casilla 01, unsigned |
| 13 | 126 | 17 | Num | [02] Gastos deducibles | casilla 02, unsigned |
| 14 | 143 | 17 | N | [03] Rendimiento neto | casilla 03, signed |
| 15 | 160 | 17 | Num | [04] 20% casilla 03 | casilla 04, unsigned |
| 16 | 177 | 17 | Num | [05] A deducir: trim anteriores | casilla 05, unsigned |
| 17 | 194 | 17 | Num | [06] Retenciones e ingresos a cta | casilla 06, unsigned |
| 18 | 211 | 17 | N | [07] Pago fraccionado previo trim | casilla 07, signed |
| 19 | 228 | 17 | Num | [08] Volumen ingresos trim (agr.) | casilla 08, unsigned |
| 20 | 245 | 17 | Num | [09] 2% casilla 08 | casilla 09, unsigned |
| 21 | 262 | 17 | Num | [10] Retenciones (agr.) | casilla 10, unsigned |
| 22 | 279 | 17 | N | [11] Pago fraccionado trim (agr.) | casilla 11, signed |
| 23 | 296 | 17 | Num | [12] Suma pagos trim ([07]+[11]) | casilla 12, unsigned |
| 24 | 313 | 17 | Num | [13] Minoración deducc. art.110.3 | casilla 13, unsigned |
| 25 | 330 | 17 | N | [14] Diferencia ([12]-[13]) | casilla 14, signed |
| 26 | 347 | 17 | Num | [15] Res. negativos ejerc. ant. | casilla 15, unsigned |
| 27 | 364 | 17 | Num | [16] Cantidades adquis. viv. hab. | casilla 16, unsigned |
| 28 | 381 | 17 | N | [17] Total ([14]-[15]-[16]) | casilla 17, signed |
| 29 | 398 | 17 | Num | [18] A deducir compl. autoliq. ant. | casilla 18, unsigned |
| 30 | 415 | 17 | N | [19] Resultado autoliquidación | casilla 19, signed |
| 31 | 432 | 1 | An | Declaración complementaria | blank or `X` |
| 32 | 433 | 13 | An | Nº justificante anterior | header previous_receipt |
| 33 | 446 | 34 | An | Domiciliación IBAN | header iban |
| 34 | 480 | 96 | An | Reservado AEAT | filler |
| 35 | 576 | 13 | An | Sello electrónico | filler |
| 36 | 589 | 12 | An | Fin registro `</T13001000>` | literal |
| — | TOTAL | 600 | — | — | — |

Total record length: **600 bytes** (DR note: "600 POSICIONES").
The envelope header adds 328 bytes (fixed) + 18 bytes (closing tag),
so the full fichero-BOE for a single-declaration Modelo 130 is:
328 + 600 + 18 = **946 bytes** (not ~878 as the plan estimated;
the plan said "roughly 878" — the actual DR total is 600 for the
page record alone; the full envelope is 946 bytes).

### Comparison with the existing export_layouts block in 130.toml

The existing block (`revision "2019-y-siguientes"`) was compared
field-by-field against the DR. Findings:

**Present and correct:**
- Envelope header: all 12 fixed fields (positions 1–328) match the DR.
- Page-01 record open tag, modelo literal, page number, close tag: correct
  (offsets 1–11, literals `<T`, `130`, `01`, `000>`).
- Complementaria indicator (offset 12, length 1): present as
  `kind = "header"`, `header_key = "complementaria"`. The DR says
  blank or `X`; the current TOML uses `data_type = "boolean"` which
  diverges from the DR's `A` type — should be `data_type = "text"`.
- Declaration type (offset 13, length 1): correct.
- NIF (offset 14, length 9): correct draft field.
- Surnames (offset 23, length 60), name (offset 83, length 20): correct.
- Filing year (offset 103, length 4), period code (offset 107, length 2):
  correct.
- Casillas 01–19 (offsets 109–431): all 19 casillas present with
  correct offsets, lengths (17), and `signed` flags matching the
  Num/N distinction in the DR. Verified:
  - Unsigned (Num): 01, 02, 04, 05, 06, 08, 09, 10, 12, 13, 15, 16, 18
  - Signed (N): 03, 07, 11, 14, 17, 19
- Previous receipt (offset 433, length 13): present.
- IBAN (offset 446, length 34): present.
- AEAT reserved filler (offset 480, length 96): present.
- Seal filler (offset 576, length 13): present.
- Page close tag `</T13001000>` (offset 589, length 12): present.
- Envelope footer with `computed_key = "envelope_closing_tag"`: present.

**Gap identified — missing field at offset 432:**

The DR row 31 defines a 1-byte `An` field at offset 432 labelled
"Declaración complementaria" (blank or `X`). This is distinct from
the `complementaria-indicator` field at offset 12 (which is the
"Indicador de página complementaria"). The DR has TWO complementaria
markers in the page record:
- Offset 12 (1 byte): `Indicador de página complementaria` — present.
- Offset 432 (1 byte): `Declaración complementaria` — MISSING from
  the current TOML.

This missing byte means the current layout maps `previous_receipt` at
offset 433 directly, which is correct in terms of offset (the DR's
offset 433 for Nº justificante confirms 432+1=433), but the
intermediate 1-byte `declaracion-complementaria` field at offset 432
is unrepresented. This is the gap to fix in P02.S05.

**Minor type divergence:**
- `modelo-130-complementaria-indicator` at offset 12 uses
  `data_type = "boolean"` but the DR defines it as type `A` (single
  character, blank or `X`). Should be `data_type = "text"`.

**No export_refs present on casillas:**
None of the 19 casilla definitions in the revision carry
`export_refs`. Adding `export_refs = ["modelo-130-casilla-NN"]` to
each casilla is part of P02.S06.

### Summary for P02

P02.S05 must:
1. Add the missing 1-byte `declaracion-complementaria` field at
   offset 432 (blank or `X`, `kind = "header"`,
   `header_key = "declaracion_complementaria"`).
2. Fix `modelo-130-complementaria-indicator` `data_type` from
   `"boolean"` to `"text"`.

P02.S06 must add `export_refs` to all 19 casillas.

The existing layout is otherwise structurally complete and correct
for the DR 13001 600-byte record and DR 13000 envelope structure.

## Tests

No production code was changed. This is a discovery step.
The gap findings above are the authoritative audit input for P02.S05.
