# Modelo 349 casillas - orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and bindings of the revision that applies to a given
`(year, period)`. Read it with tool `authority`, `query` `casillas`, `modelo`
`349`, `filing_year` and `period` (`aeat app modelo casillas 349 --year <YEAR>
--period <PERIOD>`), and treat that output as canonical. This page is
orientation only, so you know what you are looking at. Never report a casilla
value or a detail row from this page: report what the calculation produced,
with its `legal_refs` and `source_refs`.

## The declarante summary block

Modelo 349's declarante section carries four bound summary casillas, all folded
directly from the period's classified ledger:

- `decl.numero-operadores` - Numero total de operadores intracomunitarios: the
  count of distinct intra-community counterparties across every
  non-rectification clave.
- `decl.importe-operaciones` - Importe de las operaciones intracomunitarias:
  the sum of every such operation's base imponible.
- `decl.numero-rectificaciones` - Numero total de operadores intracomunitarios
  con rectificaciones: the count of distinct operators over the rectification
  rows of every clave.
- `decl.importe-rectificaciones` - Importe de las rectificaciones: the sum of
  the rectified base over the rectification rows of every clave.

The identification casillas (`decl.cambio-periodicidad`,
`decl.complementaria-sustitutiva`, `decl.nif-representante-legal`,
`decl.numero-identificativo`, `decl.numero-identificativo-anterior`) and the
sustituto casillas (`sustituto.nif`, `sustituto.apellidos-razon-social`) are
`manual`: they hold only what the person supplies.

## The operation claves

Modelo 349 reports ten claves, each mapped to a direction:

- **Outbound** (the person issued the invoice): E entregas intracomunitarias,
  M modificaciones a entregas anteriores, T triangulares (declarant as
  intermediary), S servicios prestados a otro Estado miembro, R operaciones
  referidas por un operador residente en otro Estado miembro.
- **Inbound** (the person received the invoice): A adquisiciones
  intracomunitarias, I servicios recibidos de otro Estado miembro, D
  devoluciones de adquisiciones anteriores, H adquisiciones triangulares en las
  que el declarante figura como destinatario oculto.
- **Both directions**: C correcciones a declaraciones de periodos anteriores,
  which can rectify either an outbound or an inbound operation.

## The per-operator detail rows

Alongside the declarante totals, Modelo 349 reports one row per distinct
(operator, clave) pair for the period, in the casillas `op.codigo-pais`,
`op.nif-comunitario`, `op.apellidos-razon-social`, `op.clave-operacion` and
`op.base-imponible`. The registry derives the rows from the same classified
invoices the declarante totals draw from. The casilla list marks these fields
`manual`; the calculated revision's `detail_rows` (row type, then field
key/value pairs) shows what filled them.

## The per-rectification detail rows

A rectification row reports one row per distinct (operator, clave, rectified
period) triple: the same operator identification and clave fields, plus
`rect.ejercicio-rectificado`, `rect.periodo-rectificado`,
`rect.base-rectificada` (the corrected base imponible) and `rect.base-anterior`
(the base imponible previously declared for that period), so AEAT can see both
the correction and the original figure it replaces.

## How to read it safely

- Modelo 349 has **no cuota, no tipo aplicable, and no resultado a
  ingresar/devolver**. It is a pure recapitulative informativa: never describe
  its output as a tax liability.
- The declarante totals and the detail rows are ledger-derived. A `0` on a
  declarante total, or a missing operator row, traces back to the source
  invoice's intra-community classification (direction, clave, counterpart
  country, NIF-IVA): question it there, not on the 349. Do not hand-construct
  or edit a row.
- Confirm the period's cadence before reading casillas: the registry's filing
  schedule switches Modelo 349 between quarterly (`1T`-`4T`) and monthly
  (`01`-`12`) tokens based on the `iva.intracommunity_operations_exceed_50000_eur`
  profile fact. Read operation `overview.explain` (`aeat app overview explain
  349 --year <YEAR>`) rather than assuming the prior period's cadence still
  applies.
- The same intra-community operations reported here also feed Modelo 303's
  intracomunitaria casillas for the corresponding period, but Modelo 349 has no
  automated cross-modelo reconciliation gate against Modelo 303: the two
  filings are prepared independently from the same classified ledger.
