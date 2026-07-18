# Modelo 111 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 111 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what you
are looking at. Never report a casilla value from this page — report the value
the CLI computes, with its `legal_refs`/`source_refs`.

## The nine three-casilla blocks

Modelo 111 repeats a three-casilla pattern across nine income/concept blocks:
number of perceptores, importe (base) of the payments, and importe of the
retenciones/ingresos a cuenta withheld on them.

- **Rendimientos del trabajo dinerarios (01-03)** — salaries and other cash
  labour income paid with retención withheld. Ledger-derived: perceptor count,
  taxable-base sum, and retención sum, aggregated from the
  `rendimientos_trabajo` / `rendimientos_trabajo_administrador` withholding
  schemes.
- **Rendimientos del trabajo en especie (04-06)** — non-cash labour income
  (benefit-in-kind) with ingresos a cuenta. Manual input; the taxpayer reports
  it directly.
- **Rendimientos de actividades económicas dinerarios (07-09)** — professional
  fees paid to another autónomo, with retención withheld. Ledger-derived from
  the `actividades_economicas` / `actividades_profesionales` schemes, the same
  way as 01-03.
- **Rendimientos de actividades económicas en especie (10-12)** — non-cash
  professional-fee income. Manual input.
- **Premios dinerarios (13-15)** — cash prizes subject to retención.
  Ledger-derived from the `premios` scheme.
- **Premios en especie (16-18)** — non-cash prizes. Manual input.
- **Ganancias patrimoniales forestales (19-24, dinerario + especie)** —
  forestry capital-gain payments with retención/ingresos a cuenta. Manual
  input.
- **Cesión de derechos de imagen (25-27)** — image-rights assignment
  contraprestaciones with ingresos a cuenta. Manual input.
- **Total liquidación (28-30)** — casilla 28 sums every block's retención/
  ingreso-a-cuenta casilla (03, 06, 09, 12, 15, 18, 21, 24, 27); casilla 29 is
  the operator-supplied correction from prior same-year autoliquidaciones;
  casilla 30 is 28 minus 29, the amount to pay.

## How to read it safely

- Only three blocks (01-03, 07-09, 13-15) are aggregated from the classified
  ledger. The rest are manual — a `0` there is only correct when the taxpayer
  genuinely had no such payment in the period; if in doubt, ask rather than
  trusting a computed-looking zero.
- Casilla 28 (computed) and casilla 30 (computed) come only from
  `aeat app modelo work calculate`. Reach them through the calculation, never
  by re-deriving the arithmetic.
- A nonzero perceptor count with a zero base or zero retención sum on the same
  ledger-derived block is the under-declaration shape to question before any
  export (see `cadrumo-operator-grounding` and `cadrumo-operator-safety-handoff`).
- Casilla 29's prior-autoliquidación correction is operator-supplied, not
  cross-period carried; do not assume it defaults to zero without asking
  whether an amendment applies.
- Modelo 190 folds this modelo's annual totals across all filed quarters/
  months; a period recalculated after 190 was prepared invalidates the annual
  figure and must be re-checked (see `cadrumo-preparar-modelo-390` for the parallel
  IVA case with Modelo 303/390).
