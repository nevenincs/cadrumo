# Modelo 190 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 190 --year <YEAR> --period 0A` and treat that
output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value or a per-perceptor row from this
page — report the value the CLI computes, with its `legal_refs`/
`source_refs`.

## The declarante summary block

Modelo 190's declarante section carries three summary casillas, all folded
from the year's four Modelo 111 quarters:

- **Número total de percepciones** — the count of distinct
  perceptor/clave/subclave records for the year. Computed directly from the
  per-perceptor withholding store, not by summing the four quarters'
  perceptor counts (which would double-count a perceptor paid across more
  than one quarter).
- **Importe total de las percepciones** — the sum of the year's totals across
  every Modelo 111 income block: trabajo dinerario/especie, actividades
  económicas dinerario/especie, premios dinerario/especie, ganancias
  patrimoniales dinerario/especie, and derechos de imagen. Each of those
  nine annual totals is itself the four quarters of the matching Modelo 111
  casilla (02, 05, 08, 11, 14, 17, 20, 23, 26) summed via an
  `annual_summary` relation.
- **Importe total de retenciones e ingresos a cuenta** — the year's four
  Modelo 111 casilla-28 totals summed.

## The per-perceptor detail rows

Modelo 190 is an informativa, not a self-assessment: alongside the
declarante totals it reports one row per distinct (perceptor, clave,
subclave) combination for the year — the perceptor's tax id and legal name,
the clave/subclave (the income-and-withholding-scheme code), the dinerario
and especie amounts perceived, the retención practicada, and the ingreso a
cuenta. These rows come from the same withholding store the declarante
totals are computed from; they are not a separate manual entry surface.

## How to read it safely

- Every quarter's fold-in depends on that Modelo 111 quarter being
  calculated and stable. A quarter recalculated after Modelo 190 was
  prepared invalidates the annual figures — re-check each quarter's
  revision, then recalculate Modelo 190, never edit its casillas by hand
  (see `cadrumo-preparar-modelo-390` for the parallel IVA case with Modelo 303/390).
- The fold-in relations select only the quarterly Modelo 111 period tokens
  (`1T`-`4T`). If the taxpayer's Modelo 111 cadence is monthly instead, the
  automatic annual fold-in does not draw on those monthly filings —
  confirm cadence with `aeat app overview explain 111 --year <YEAR>` before
  assuming the 190's totals are complete.
- Modelo 111's manual (non-ledger-derived) blocks — trabajo en especie,
  ganancias patrimoniales forestales, cesión de derechos de imagen — fold
  into Modelo 190 through the same relations as the ledger-derived blocks.
  A `0` at the source Modelo 111 quarter folds forward as `0`; question a
  suspicious zero on the Modelo 111 quarter itself, not on the 190.
- A nonzero perceptor count with a zero total percepciones or zero total
  retenciones on the declarante summary is the under-declaration shape to
  question before any export (see `cadrumo-operator-grounding` and
  `cadrumo-operator-safety-handoff`).
