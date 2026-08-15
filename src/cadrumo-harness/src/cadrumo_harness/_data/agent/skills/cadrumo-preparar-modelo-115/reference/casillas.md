# Modelo 115 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 115 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what you
are looking at. Never report a casilla value from this page — report the value
the CLI computes, with its `legal_refs`/`source_refs`.

## The five casillas

Modelo 115 has one three-casilla ledger-derived block plus a two-casilla
liquidación tail — far smaller than Modelo 111's nine income/concept blocks,
because the form covers a single concept (retención on urban rental paid to
a landlord).

- **Número de perceptores (01)** — the distinct count of landlords
  (perceptores) the taxpayer paid rent to, and withheld retención from, in
  the period. Ledger-derived: aggregated from the urban-rental withholding
  scheme.
- **Base de retenciones e ingresos a cuenta (02)** — the sum of the taxable
  rent base subject to retención across every payment in the period.
  Ledger-derived, same scheme as 01.
- **Retenciones e ingresos a cuenta (03)** — computed as 19% of casilla 02
  (`irpf.urban_rental_withholding_rate`). Reach it only through
  `aeat app modelo work calculate`; never re-derive the percentage yourself.
- **Resultado de anteriores declaraciones (04)** — manual input: an
  operator-supplied same-year prior-quarter correction, used only when
  amending. It is not cross-period carried; ask whether an amendment applies
  before assuming zero.
- **Resultado a ingresar (05)** — computed as casilla 03 minus casilla 04,
  the amount to pay.

## How to read it safely

- Casillas 01 and 02 are the only ledger-aggregated fields. There is no
  en-especie or additional income block to check for manual entry, unlike
  Modelo 111 — Modelo 115 is a single-concept form.
- Casilla 03 (computed) and casilla 05 (computed) come only from
  `aeat app modelo work calculate`. Reach them through the calculation, never
  by re-deriving the arithmetic.
- A nonzero perceptor count (01) with a zero base or zero retención sum
  (02/03) is the under-declaration shape to question before any export (see
  `cadrumo-operator-grounding` and `cadrumo-operator-safety-handoff`).
- Casilla 04's prior-autoliquidación correction is operator-supplied, not
  cross-period carried; do not assume it defaults to zero without asking
  whether an amendment applies.
- Modelo 180 (not Modelo 190) folds this modelo's annual base and
  retenciones totals across all four filed quarters, and independently
  computes its own distinct-perceptor count rather than summing the
  quarterly counts (a landlord paid across multiple quarters would otherwise
  be double-counted). A quarter recalculated after Modelo 180 was prepared
  invalidates the annual figure and must be re-checked (see
  `cadrumo-preparar-modelo-390` for the parallel IVA case with Modelo 303/390).
