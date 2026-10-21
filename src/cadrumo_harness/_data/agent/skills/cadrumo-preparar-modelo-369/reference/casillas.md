# Modelo 369 casillas - orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the esquema that applies to a given
`(year, period)`. Read it with tool `authority`, `query` `casillas`, `modelo`
`369`, `filing_year` and `period` (`aeat app modelo casillas 369 --year <YEAR>
--period <PERIOD>`), and treat that output as canonical. This page is
orientation only, so you know what esquema and shape you are looking at. Never
report a casilla value from this page: report the value the calculation
produced, with its `legal_refs` and `source_refs`.

Each esquema is its own registry revision, and the period token picks it.

## Esquema Unión (period `1T`/`2T`/`3T`/`4T`)

Covers intra-EU distance sales of goods, electronic-interface-facilitated
supplies, and services from an EU-established taxable person to consumers in
other member states (LIVA art. 163 unvicies-quatervicies).

Casillas the classified ledger fills (`input_kind` `bound`), all from issued
invoices at the general rate:

- `iva.union.de.services-cuota` - destination Germany, services, from invoices
  classified `oss_union_services`.
- `iva.union.fr.services-cuota` - destination France, services, from invoices
  classified `oss_union_services`.
- `iva.union.de.goods-distance-cuota` - destination Germany, distance sales and
  interface-facilitated goods, from invoices classified
  `oss_union_goods_distance_sale` or `oss_union_goods_interface_facilitated`.

`iva.union.cuota-total` is computed and labelled "Subtotal parcial: servicios a
Alemania y Francia y bienes a Alemania (sin correcciones)". The rest of the
revision is computed: per-member-state settlement casillas
(`iva.union.resultado.<country>.*`, with servicios, bienes, totals,
correcciones and amounts to pay or recover) and control casillas
(`iva.union.control.*`).

## Esquema Exterior (period `EXT-1T`/`EXT-2T`/`EXT-3T`/`EXT-4T`)

Covers services from a non-EU-established taxable person to EU consumers (LIVA
art. 163 octiesdecies-vicies). Same quarterly cadence as Esquema Unión but a
distinct `EXT-`-prefixed period-token family and a distinct revision.

- Bound: `iva.exterior.de.services-cuota` - destination Germany, services, from
  invoices classified `external_scheme_services`, general rate.
- Computed: `iva.exterior.cuota-total`, labelled "Subtotal parcial: servicios a
  Alemania (sin correcciones)", the per-member-state settlement casillas
  (`iva.exterior.resultado.<country>.*`) and the control casillas.

## Esquema Importación / IOSS (period `01`-`12`, monthly)

Covers distance sales of imported goods with intrinsic value of 150 EUR or less
(LIVA art. 163 quinvicies-octovicies). Monthly cadence, distinct from both
quarterly esquemas.

- Bound: `iva.importacion.de.low-value-cuota` - destination Germany, from
  invoices classified `ioss_distance_sale_low_value`, general rate.
- Computed: `iva.importacion.cuota-total`, labelled "Subtotal parcial:
  importaciones a Alemania (sin correcciones)", the per-member-state settlement
  casillas (`iva.importacion.resultado.<country>.*`) and the control casillas.

## How to read it safely

- A bound cuota casilla is never a manual entry. If a destination's cuota looks
  wrong, fix the ledger classification and calculate again; do not edit a
  casilla to a number you prefer.
- Only the destinations and rates listed above are filled from the ledger. The
  totals say "Subtotal parcial": say what they cover, and do not present them
  as the whole OSS/IOSS liability.
- Computed casillas come only from the calculation. Read them from the
  revision, never by hand-summing rows yourself.
- A classified OSS/IOSS invoice whose cuota no binding consumes is the
  under-declaration shape the advisory about IVA consumed by no casilla exists
  to catch. Act on it before export rather than assuming a silent zero.
- The three esquemas are independent work units with independent revisions,
  even when they share a filing year: a taxpayer enrolled in more than one
  esquema prepares, verifies and exports each separately.
