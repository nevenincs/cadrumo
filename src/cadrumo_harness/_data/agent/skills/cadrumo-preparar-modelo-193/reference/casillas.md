# Modelo 193 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 193 --year <YEAR> --period 0A` and treat that
output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value or a per-perceptor row from this
page — report the value the CLI computes, with its `legal_refs`/
`source_refs`.

## The declarante summary block

Modelo 193's declarante section carries three summary casillas:

- **Numero total de perceptores** — the number of type-2 perceptor records,
  as every record design states (a perceptor on several records counts once
  per record). Not a sum of the quarters' counts and not a count of
  distinct NIFs.
- **Base retenciones e ingresos a cuenta total** — for ejercicio 2024, the
  year's four Modelo 123 casilla-`06` totals summed via an `annual_summary`
  relation; in the other supported years, the sum over the type-2 records.
- **Retenciones e ingresos a cuenta total** — for ejercicio 2024, the year's
  four Modelo 123 casilla-`09` totals summed via an `annual_summary`
  relation; in the other supported years, the sum over the type-2 records.

## The per-perceptor detail rows

Modelo 193 is an informativa, not a self-assessment: alongside the
declarante totals it reports one type-2 record per perceptor and clave (and,
from 2025, ejercicio de devengo) —
the perceptor's tax id and legal name, the clave (the capital-income
category and withholding-scheme code, e.g. intereses de cuentas or
dividendos), the amount perceived (dinerario), and the retención practicada.
These rows come from the same withholding store the declarante totals are
computed from; they are not a separate manual entry surface.

## How to read it safely

- Where the totals fold the Modelo 123 quarters (ejercicio 2024), each
  quarter must be calculated and stable. A quarter recalculated after Modelo 193 was
  prepared invalidates the annual figures — re-check each quarter's
  revision, then recalculate Modelo 193, never edit its casillas by hand
  (see `cadrumo-preparar-modelo-190` for the parallel retenciones case with
  Modelo 111/190).
- The fold-in relations select only the quarterly Modelo 123 period tokens
  (`1T`-`4T`). Modelo 123 has no monthly variant in this revision, so a
  cadence check is not needed the way it is for Modelo 111/190.
- Every declarante total and every perceptor row is ledger-derived; there is
  no manual (non-ledger-derived) income block on Modelo 193. A `0` on a
  total traces back to its source (the perceptor records, or for 2024 the
  Modelo 123 quarter) — question it there, not on the 193.
- A nonzero perceptor count with a zero total base or zero total retenciones
  on the declarante summary is the under-declaration shape to question
  before any export (see `cadrumo-operator-grounding` and
  `cadrumo-operator-safety-handoff`).
