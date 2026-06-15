---
tags:
  - '#research'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-modelo-130-pagos-fraccionados-carry-adr]]'
---

# `modelo-130-pagos-fraccionados-carry` research: investigation backing the decision

This research captures the investigation that backed the `modelo-130-pagos-fraccionados-carry` ADR.

## Findings

Modelo 130 (IRPF pago fraccionado, estimación directa) accumulates from the start of
the ejercicio: casilla `01` (Ingresos) is a year-to-date cumulative sum, so casilla
`04` (Importe del pago fraccionado) is the cumulative 20% pago fraccionado on the YTD
rendimiento neto. The official resultado of apartado I nets out prior payments —
casilla `07` = `04` − `05` − `06` (AEAT instrucciones; RD 439/2007 art. 110), where
casilla `05` ("Pagos fraccionados anteriores") carries the prior quarters' payments
forward.

In the committed registry, casilla `05` is `input_kind = "manual"` with no binding, so
a cumulative 2T / 3T / 4T `calculate` leaves it at zero, casilla `07` fails to deduct
the prior payment, and the resultado over-states the amount owed. The investigation
concluded the fix is a same-modelo `previous_filing` carry binding for casilla `05`,
resolved through the canonical aggregation mechanism rather than a parallel resolver.
