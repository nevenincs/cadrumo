# Modelo 369 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the esquema/revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 369 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what
esquema and shape you are looking at. Never report a casilla value from this
page — report the value the CLI computes, with its `legal_refs`/
`source_refs`.

## Esquema Unión (`--period 1T`/`2T`/`3T`/`4T`)

Covers intra-EU distance sales of goods, electronic-interface-facilitated
supplies, and services from an EU-established taxable person to consumers in
other member states (LIVA art. 163 unvicies-quatervicies).

- **Per-destination services cuota** — one casilla per destination member
  state for services rendered (e.g. cuota IVA destino DE — servicios
  prestados, cuota destino FR — servicios prestados). Ledger-derived from
  issued invoices classified `oss_union_services` for that destination.
- **Per-destination goods-distance cuota** — one casilla per destination
  member state for distance sales and interface-facilitated goods supplies.
  Ledger-derived from invoices classified `oss_union_goods_distance_sale` or
  `oss_union_goods_interface_facilitated`.
- **Total cuota IVA Unión** — computed casilla summing every
  destination/supply-kind cuota above via a registry formula.

## Esquema Exterior (`--period EXT-1T`/`EXT-2T`/`EXT-3T`/`EXT-4T`)

Covers services from a non-EU-established taxable person to EU consumers
(LIVA art. 163 octiesdecies-vicies). Same quarterly cadence as Esquema Unión
but a distinct `EXT-`-prefixed period-token family, and a distinct revision.

- **Per-destination services cuota** — one casilla per destination member
  state, ledger-derived from invoices classified `external_scheme_services`.
- **Total cuota IVA Exterior** — computed casilla summing every destination
  cuota above.

## Esquema Importación / IOSS (`--period 01`-`12`, monthly)

Covers distance sales of imported goods with intrinsic value at or below 150
EUR (LIVA art. 163 quinvicies-octovicies). Monthly cadence, distinct from
both quarterly esquemas.

- **Per-destination low-value-goods cuota** — one casilla per destination
  member state, ledger-derived from invoices classified
  `ioss_distance_sale_low_value`.
- **Total cuota IVA Importación** — computed casilla summing every
  destination cuota above.

## How to read it safely

- Every cuota casilla is `input_kind = "bound"`, resolved by the
  `ledger_oss_aggregation` source from the classified ledger — never a
  manual entry. If a destination's cuota looks wrong, fix the ledger
  classification and re-calculate; do not edit a casilla to a number you
  prefer.
- The total casilla is `input_kind = "computed"`; read it only from
  `aeat app modelo work calculate` / `work revision`, never by hand-summing
  the per-destination rows yourself.
- A classified OSS/IOSS invoice whose cuota no binding consumes is the
  under-declaration shape the unconsumed-declarable-IVA advisory exists to
  catch; act on it before export rather than assuming a silent zero.
- The three esquemas are independent work units with independent revisions,
  even when they share a filing year — a taxpayer enrolled in more than one
  esquema prepares, verifies, and exports each separately.
