# Modelo 130 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 130 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value from this page — report the value the CLI
computes, with its `legal_refs`/`source_refs`.

## The direct-estimation block (the common case)

Modelo 130 Section I covers activities under direct estimation (estimación
directa). The load-bearing casillas an operator reads:

- **Ingresos** — computable income for the quarter, accumulated from the start of
  the year. Derived from the classified ledger; an input to the calculation, not
  something you total by hand.
- **Gastos** — deductible expenses for the quarter, accumulated. Also ledger-
  derived, after business-use ratios are applied.
- **Rendimiento** — net result (ingresos minus gastos). Computed by the engine.
- **Instalment base / rate casilla** — the percentage applied to a positive
  rendimiento to obtain the quarter's instalment. Read the rate and its
  `legal_refs` from the calculated casilla; do not assume a rate.
- **Pagos fraccionados anteriores** — instalments already paid in earlier quarters
  of the same year, subtracted so each quarter pays only its increment.
- **Retenciones e ingresos a cuenta** — withholdings already suffered, subtracted.
- **Result casilla** — the amount to pay (a positive result) for the quarter.

## How to read it safely

- Inputs (ingresos, gastos, retenciones) come from the classified ledger and the
  profile. If they look wrong, fix the ledger and re-calculate; do not edit a
  casilla to a number you prefer.
- Computed casillas (rendimiento, the instalment, the result) come only from
  `aeat app modelo work calculate`. Reach them through the calculation, never by
  re-deriving the arithmetic.
- A positive rendimiento with a zero instalment, or positive ingresos with a zero
  result and no declared reduction, is the under-declaration shape to question
  before any export (see `cadrumo-operator-grounding` and `cadrumo-operator-safety-handoff`).
- Cross-quarter carry (the prior-instalment subtraction) is revision-stamped; if a
  prior quarter's value cannot be confirmed, surface the advisory rather than
  trusting a silent zero.
