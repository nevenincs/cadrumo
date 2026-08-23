# Modelo 180 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 180 --year <YEAR> --period 0A` and treat that
output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value or a per-perceptor row from this
page — report the value the CLI computes, with its `legal_refs`/
`source_refs`.

## The declarante summary block

Modelo 180's declarante section carries three summary casillas, all folded
from the year's four Modelo 115 quarters:

- **Número total de perceptores** — the DISTINCT count of landlords
  (perceptores) paid rent-withholding across the year. Computed directly
  from the per-perceptor retención store, not by summing the four quarters'
  Modelo 115 perceptor counts (which would double-count a landlord paid
  across more than one quarter).
- **Base retenciones e ingresos a cuenta total** — the year's four Modelo
  115 casilla-02 totals (each quarter's taxable rental base) summed via a
  relation fold-in.
- **Retenciones e ingresos a cuenta total** — the year's four Modelo 115
  casilla-03 totals (each quarter's own retenciones) summed via a relation
  fold-in.

## The per-perceptor detail rows are manual

Modelo 180 is an informativa, not a self-assessment: alongside the
declarante totals it reports one row per landlord (perceptor) paid during
the year — tax id, legal name, the leased inmueble's address and cadastral
reference, the modalidad and porcentaje de retención, and the base and
retenciones amounts attributable to that landlord.

Unlike Modelo 190's per-perceptor rows (computed from the withholding
store), **Modelo 180's per-perceptor base and retenciones casillas are
manual input** in the registry (`input_kind = "manual"`). The declarante
totals fold automatically from the four Modelo 115 quarters; the
per-perceptor rows that should sum to those totals do not. Confirm every
landlord paid during the year has an entered row and that the rows sum to
the declarante totals before export — `calculate` reporting `success` does
not by itself mean the per-perceptor breakdown is complete.

## How to read it safely

- Every quarter's fold-in depends on that Modelo 115 quarter being
  calculated and stable. A quarter recalculated after Modelo 180 was
  prepared invalidates the annual figures — re-check each quarter's
  revision, then recalculate Modelo 180, never edit its declarante casillas
  by hand (see `cadrumo-preparar-modelo-390` for the parallel IVA case with Modelo
  303/390).
- Modelo 115 is quarterly-only (`1T`-`4T`), so unlike Modelo 111/190 there
  is no monthly-cadence ambiguity to confirm before assuming the fold-in
  covers the full year.
- A nonzero perceptor count with a zero total base or zero total
  retenciones on the declarante summary is the under-declaration shape to
  question before any export (see `cadrumo-operator-grounding` and
  `cadrumo-operator-safety-handoff`).
- The per-perceptor rows are manual: a declarante summary that reconciles
  against the four Modelo 115 quarters does not guarantee the per-perceptor
  breakdown is complete or that it sums to those totals. Check it
  explicitly — `verify` only gates the declarante-level fold-in equality,
  not the per-perceptor rows.
