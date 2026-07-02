# Modelo 202 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 202 --year <YEAR> --period <PERIOD>` and treat that
output as canonical; this page is orientation only, so you know which
modalidad and lane a casilla belongs to. Never report a casilla value from
this page - report the value the CLI computes, with its
`legal_refs`/`source_refs`.

## The modalidad map

Modelo 202 has two mutually exclusive top-level modalidades, selected by the
registry's INCN gate (`derive_modelo_202_modality`, LIS art. 40.3) - never by
the taxpayer's preference or the entity's size assumed from memory:

- **Modalidad art. 40.2 (base cuota anterior)** - available only when INCN
  over the prior twelve months does not exceed EUR 6.000.000. Casilla `01`
  (base del pago fraccionado) carries in the prior Modelo 200's cuota líquida
  (`DP200014B:00592`) as a cross-modelo `relation_prefill`; casilla `02`
  (resultado de la declaración anterior, for complementarias) is manual;
  casilla `03` ("A ingresar") is the computed result of this lane.
- **Modalidad art. 40.3 (base corrida del ejercicio)** - always available, and
  mandatory when INCN exceeds EUR 6.000.000. Starts from the entity's own
  accounting result for the year-to-date (casilla `04`, resultado contable
  después del IS, manual) plus correcciones (aumentos `38`, disminuciones
  `39`) to reach the base imponible previa (casilla `13`, computed), then
  applies one of two mutually exclusive rate sub-lanes (below) to reach
  casilla `32` (resultado), then casilla `34` ("Cantidad a ingresar, mayor de
  claves [32] y [33]").

## The art. 40.3 rate sub-lanes: B1 vs B2

Within the art. 40.3 modalidad, casilla `32` sums two alternative rate
computations that AEAT's own instructions describe as "clave [18] (o clave
[26])" - a filer completes exactly one lane's inputs and leaves the other
blank:

- **B1 (caso general, un único tipo de gravamen)** - casillas `16` (base,
  computed from `13` plus/minus prior adjustments), `17` (porcentaje, manual),
  `47`/`48`/`40`/`49` (bonificaciones/retenciones/volumen/pagos previos)
  feeding casilla `18` (resultado previo B1).
- **B2 (casos específicos, varios tipos de gravamen)** - separate base/rate
  pairs per tramo: `19`/`20` (tipo 1), `22`/`23` or similar (tipo 2), `61`/`62`
  (tipo 3, **2025-only**), `64`/`65` (tipo 4, **2025-only**), each producing a
  computed importe (`21`, `24`/`25`, `63`, `66` respectively), summed with
  `50` (compensación) and `42` (compensación de cuotas negativas, cooperativas)
  into casilla `26` (resultado previo B2).

Casilla `32` = `18 + 26` (the registry's additive reproduction of "o"); the
registry BLOCKS a filing where both `18` and `26` are positive (they must be
mutually exclusive), but does not reject an upstream path that populates both
lanes' underlying manual inputs before that check runs - watch for a taxpayer
who mistakenly fills both.

## Casilla `33` — the known gap

Casilla `33` ("Mínimo a ingresar, CN >= 10 millones euros") is a manual input
with **no formula, no binding, and no verification guard** in any revision.
The underlying large-taxpayer minimum-payment-on-account floor is not grounded
in this codebase's legal catalogue. If the taxpayer's INCN is at or above EUR
10.000.000, ask explicitly whether the floor applies - the CLI will not warn
you. Casilla `34` is `max(32, 33)`, so a wrongly-blank `33` silently
under-declares the instalment for a large taxpayer whose floor would exceed
the ordinary `32` result.

## How to read it safely

- Inputs fall into three provenance classes: manually-entered accounting
  facts with no ledger counterpart (`04`, most B1/B2 bases and rates - route
  to the role that owns operator-entered facts), profile-sourced (INCN, via
  `incn_prior_12_months`), and cross-modelo/cross-period folded-in (the prior
  Modelo 200 cuota into casilla `01`; the year's own earlier instalments'
  casilla `34` summed into the current instalment's credit). Never edit a
  casilla to a number you prefer regardless of provenance.
- Computed casillas (`03`, `13`, `16`, `18`, `21`/`24`/`25`/`63`/`66`, `26`,
  `32`, `34`) come only from `aeat app modelo work calculate`. Reach them
  through the calculation, never by re-deriving the bracket, sum, or
  percentage arithmetic.
- A strictly positive `04` with a zero base imponible previa (`13`) and no
  declared corrección explaining it, or a positive B2 tramo base (`61`/`64`)
  with a zero computed importe (`63`/`66`), is the under-declaration shape to
  question before export - both are non-blocking advisories, legitimate in a
  loss-making period, so confirm rather than assume either way.
- Casilla `33` carries no guard at all (see above) - this is a documented gap,
  not an oversight to route past silently.
- The modalidad and B1/B2 sub-lane are gated by data the taxpayer declares
  (INCN, which manual inputs are populated), never by the entity's legal form
  or size assumed from memory. Read which lane the calculated revision
  actually populated.
