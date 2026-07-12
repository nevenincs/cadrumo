# Synthetic AEAT filing-detail HTML fixtures

These fixtures are hand-authored to exercise the read-only fetchers
under `src/aeat/remote/filings/`. They carry no real taxpayer data and
no real AEAT content; every NIF, CSV, expediente identifier, and
monetary value is synthetic.

Fixtures:

- `modelo_130_happy.html` — canonical Modelo 130 quarterly filing with
  every tracked casilla populated and a `Presentada` status.
- `modelo_130_missing_casilla.html` — Modelo 130 filing with casilla
  02 and 06 absent from the table; exercises the fetcher's
  missing-casilla fallback to `Decimal("0")`.
- `modelo_303_happy.html` — canonical Modelo 303 quarterly IVA
  return with the six tracked casillas populated and a receipt
  (`Total a ingresar`) label present.
- `modelo_303_unknown_status.html` — Modelo 303 filing with a
  status string AEAT has not been seen emitting before; exercises
  the `RemoteFilingStatus.UNKNOWN` fallback and the warning log.
- `modelo_303_complementaria.html` — Modelo 303 filing amending a
  prior expediente; exercises the `complementaria_of` linkage.
- `modelo_390_happy.html` — canonical Modelo 390 annual IVA summary
  with the five tracked casillas populated.

Keep the fixtures minimal; the goal is unambiguous test input, not a
faithful replica of the AEAT page layout.
