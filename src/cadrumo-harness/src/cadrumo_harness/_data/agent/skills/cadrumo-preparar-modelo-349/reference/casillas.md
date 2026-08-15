# Modelo 349 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and bindings of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 349 --year <YEAR> --period <PERIOD>` and treat that
output as canonical; this page is orientation only, so you know what you are
looking at. Never report a casilla value or a detail row from this page —
report the value the CLI computes, with its `legal_refs`/`source_refs`.

## The declarante summary block

Modelo 349's declarante section carries four summary casillas, all folded
directly from the period's classified ledger:

- **Numero total de operadores intracomunitarios** — the count of distinct
  intra-community counterparties across every non-rectification clave,
  computed as a `count_distinct` over the classified-invoice store.
- **Importe de las operaciones intracomunitarias** — the sum of every such
  operation's base imponible.
- **Numero total de operadores intracomunitarios con rectificaciones** — the
  same count, scoped to clave C (correcciones) rows only.
- **Importe de las rectificaciones** — the sum of the rectified base delta,
  scoped to clave C rows only.

## The operation claves

Modelo 349 reports ten claves, each mapped to a canonical direction:

- **Outbound** (the declarant issued the invoice — bound from
  `collectible_invoice`): E entregas intracomunitarias, M modificaciones a
  entregas anteriores, T triangulares (declarant as intermediary), S
  servicios prestados a otro Estado miembro, R operaciones referidas por un
  operador residente en otro Estado miembro.
- **Inbound** (the declarant received the invoice — bound from
  `payable_invoice`): A adquisiciones intracomunitarias, I servicios
  recibidos de otro Estado miembro, D devoluciones de adquisiciones
  anteriores, H adquisiciones triangulares en las que el declarante figura
  como destinatario oculto.
- **Both directions**: C correcciones a declaraciones de periodos
  anteriores, which can rectify either an outbound or an inbound operation
  and is unioned from both binding sets, de-duplicated by operation id.

## The per-operator detail rows

Alongside the declarante totals, Modelo 349 reports one row per distinct
(operator, clave) pair for the period: the counterparty's country code
(`codigo pais`), NIF-IVA, apellidos y nombre o razón social, the clave, and
the base imponible. These rows are ledger-derived from the same classified
invoices the declarante totals draw from; they are not a separate manual
entry surface.

## The per-rectification detail rows

A rectification row reports one row per distinct (operator, clave, rectified
period) triple: the same operator identification and clave fields, plus the
rectified ejercicio and periodo, the corrected base imponible
(`base rectificada`), and the base imponible previously declared for that
period (`base anterior`) — so AEAT can see both the correction and the
original figure it replaces.

## How to read it safely

- Modelo 349 has **no cuota, no tipo aplicable, and no resultado a
  ingresar/devolver**. It is a pure recapitulative informativa: never
  describe its output as a tax liability.
- Every casilla and every detail row is ledger-derived; there is no manual
  (non-ledger-derived) block. A `0` on a declarante total, or a missing
  operator row, traces back to the source invoice's intra-community
  classification (direction, clave, counterpart country, NIF-IVA) — question
  it there, not on the 349 (see `cadrumo-operator-grounding` and
  `cadrumo-operator-safety-handoff`).
- Confirm the period's cadence before reading casillas: the registry's
  filing schedule switches Modelo 349 between quarterly (`1T`-`4T`) and
  monthly (`01`-`12`) tokens based on the
  `iva.intracommunity_operations_exceed_50000_eur` profile fact — read
  `aeat app overview explain 349 --year <YEAR>` rather than assuming the
  prior period's cadence still applies.
- The same intra-community operations reported here also feed Modelo 303's
  intracomunitaria casillas for the corresponding period, but Modelo 349 has
  no automated cross-modelo reconciliation gate against Modelo 303 — the two
  filings are prepared independently from the same classified ledger.
