# Modelo 322 casillas - orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with tool `authority`, `query` `casillas`, `modelo`
`322`, `filing_year` and `period` (`aeat app modelo casillas 322 --year <YEAR>
--period <PERIOD>`), and treat that output as canonical. This page is
orientation only, so you know what shape you are looking at. Never report a
casilla value from this page: report the value the calculation produced, with
its `legal_refs` and `source_refs`.

## Revisions

Modelo 322 is monthly only (period tokens `01`-`12`). The registry carries
four revisions: 2008-2022 (selected for filing year 2022), 2023, 2024-2025 and
2026 onward. The casilla list you read for the year and period you are
preparing says which one applies.

## What the ledger fills, and what stays manual

The printed form is large (the 2024-2025 revision lists 227 casillas), and
almost all of it is `manual` input kind: intragroup operations, recargo de
equivalencia, prorratas, the differentiated-deduction groups and the
identification data (`decl.entidad-dominante-nif`, `decl.grupo-numero`,
`decl.prorrata-especial`). A manual casilla holds a value only if the person
gave you one; do not fill it with a figure you worked out.

The casillas the classified ledger fills (`input_kind` `bound`) are:

- **Cuota devengada, per tipo** - `iva.repercutido.general` (21%),
  `iva.repercutido.reducido` (10%) and `iva.repercutido.super-reducido` (4%),
  from this member's own repercutido lines classified at that rate.
- **Cuota autorepercutida intracomunitaria** -
  `iva.autorepercutido.intracomunitaria`, inversión del sujeto pasivo on
  intra-community acquisitions (LIVA art. 84).
- **Cuota deducible interiores** - `iva.soportado.interiores`, this member's
  soportado lines on domestic operations.

Three casillas are computed from those:

- `iva.cuota-devengada-total` - the three repercutido casillas plus the
  autorepercutido casilla.
- `iva.cuota-deducible-total` - the soportado casilla plus the autorepercutido
  casilla (the autorepercutido cuota is simultaneously devengada and deducible
  under the reverse-charge mechanism).
- `iva.resultado-regimen-general` - cuota devengada total minus cuota deducible
  total. This is THIS MEMBER's own result, not the group's.

## How to read it safely

- A bound casilla is never a manual entry. If a cuota looks wrong, fix the
  ledger classification and calculate again; do not edit a casilla to a number
  you prefer.
- Computed casillas come only from the calculation. Read them from the
  revision, never by hand-summing the bound casillas yourself.
- A classified IVA line whose cuota no binding consumes is the
  under-declaration shape the advisory about IVA consumed by no casilla exists
  to catch. Act on it before export rather than assuming a silent zero.
- The individual `iva.resultado-regimen-general` is one input among several the
  entidad dominante's Modelo 353 brings together across every member for the
  same month. Do not treat it as, or report it as, the group's final
  ingreso/devolución outcome; that determination happens only inside the
  Modelo 353 work unit.
