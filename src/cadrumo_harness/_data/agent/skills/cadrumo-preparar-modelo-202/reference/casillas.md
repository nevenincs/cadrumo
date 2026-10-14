# Modelo 202 casillas - orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with tool `authority`, `query` `casillas`, `modelo`
`202`, `filing_year` and `period` (`aeat app modelo casillas 202 --year <YEAR>
--period <PERIOD>`), and treat that output as canonical. This page is
orientation only, so you know which modalidad and lane a casilla belongs to.
Never report a casilla value from this page: report the value the calculation
produced, with its `legal_refs` and `source_refs`.

## The modalidad map

Modelo 202 has two top-level modalidades, selected by the registry's INCN gate
(LIS art. 40.3) and reported as the revision's `modality`; never by the
taxpayer's preference or the entity's size assumed from memory:

- **Modalidad art. 40.2 (base cuota anterior)** - available only when INCN over
  the prior twelve months does not exceed EUR 6.000.000. Casilla `01` (base del
  pago fraccionado) is bound to the prior Modelo 200's cuota del ejercicio a
  ingresar o a devolver (`DP200014B:00599`) through a cross-modelo relation;
  casilla `02` (resultado de la declaración anterior, for complementarias) is
  manual; casilla `03` ("A ingresar") is computed as casilla `01` times the
  modalidad's percentage, minus casilla `02`.
- **Modalidad art. 40.3 (base corrida del ejercicio)** - always available, and
  mandatory when INCN exceeds EUR 6.000.000. It starts from the entity's own
  accounting result for the year to date (casilla `04`, resultado contable
  después del IS, manual) plus correcciones to reach the base imponible previa
  (casilla `13`, computed), then applies one of two mutually exclusive rate
  sub-lanes (below) to reach casilla `32` (resultado), then casilla `34`
  ("Cantidad a ingresar, mayor de claves [32] y [33]").

## The base chain (art. 40.3)

- Casilla `13` (base imponible previa) = `04` + `38` - `39`.
- Casilla `38` (total correcciones, aumentos) = `05` + `07`; casilla `39` (total
  correcciones, disminuciones) = `06` + `37` + `08`. All of `05`-`08` and `37`
  are manual.
- Casilla `16` (B1 base del pago fraccionado) = the larger of 0 and `13` - `44`
  - `14` + `45` - `46`. Casillas `14` (compensación de bases negativas), `44`
  (remanente de reserva de capitalización), `45`/`46` (reserva de nivelación,
  art. 105 LIS, aumentos/disminuciones) are manual.

## The art. 40.3 rate sub-lanes: B1 vs B2

Within art. 40.3, casilla `32` takes two alternative rate computations that
AEAT's own instructions describe as "clave [18] (o clave [26])". A filer
completes exactly one lane's inputs and leaves the other blank:

- **B1 (caso general, un único tipo de gravamen)** - casilla `18` (resultado
  previo B1) = `16` x `17` / 100 + `47` + `48` - `40` - `49`. Casilla `17` is the
  porcentaje, `47` the dotaciones del art. 11.12 LIS, `48`/`49` the reserva de
  nivelación convertida (aumentos/disminuciones), `40` the compensación de
  cuotas negativas (cooperativas); all manual.
- **B2 (casos específicos, varios tipos de gravamen)** - casilla `19` (base del
  pago fraccionado) is manual, then one base/porcentaje/importe group per tipo:
  `20`/`21`/`22` (tipo 1), `23`/`24`/`25` (tipo 2) and, 2025-only,
  `61`/`62`/`63` (tipo 3) and `64`/`65`/`66` (tipo 4). The base and porcentaje
  are manual; the importe (`22`, `25`, `63`, `66`) is computed as base x
  porcentaje / 100. Casilla `26` (resultado previo B2) is built from `22`, `25`,
  `63`, `66`, `50` (dotaciones art. 11.12, cooperativas), `42` (compensación de
  cuotas negativas, cooperativas), `51` and `52` (reserva de nivelación,
  aumentos/disminuciones).

Casilla `32` = ((`18` + `26`) - `27` - `28`) x `29` / 100 - `30` - `31`, where
`27` is bonificaciones, `28` retenciones e ingresos a cuenta, `29` the volumen
de operaciones en territorio común (%), `30` the pagos fraccionados de periodos
anteriores (bound, see below) and `31` the resultado de la declaración anterior
(complementaria). The formula adds both lanes, so the registry does not need a
lane flag; verification blocks a filing where both `18` and `26` are positive,
but a taxpayer who mistakenly fills both lanes' manual inputs is still the thing
to watch for before that check runs.

Casilla `30` is bound: the sum of casilla `34` of the year's earlier
instalments, for `2P` and `3P`.

## Casilla `33` - the known gap

Casilla `33` ("Mínimo a ingresar, CN >= 10 millones euros") is a manual input
with **no formula, no binding, and no verification guard** in any revision. The
underlying large-taxpayer minimum-payment-on-account floor is not grounded in
the bundled legal catalogue. If the person's INCN is at or above EUR
10.000.000, ask explicitly whether the floor applies; Cadrumo will not warn you.
Casilla `34` is the larger of `32` and `33`, so a wrongly blank `33` silently
under-declares the instalment for a large taxpayer whose floor would exceed the
ordinary `32` result.

## How to read it safely

- Inputs fall into three provenance classes: manually entered accounting facts
  with no ledger counterpart (`04` and most B1/B2 bases and rates; ask the
  person for them), profile-sourced (INCN, from `incn_prior_12_months`), and
  cross-modelo or cross-period folded in (the prior Modelo 200 cuota into
  casilla `01`; the year's own earlier instalments' casilla `34` into casilla
  `30`). Never edit a casilla to a number you prefer, whatever its provenance.
- Computed casillas (`03`, `13`, `16`, `18`, `22`, `25`, `63`, `66`, `26`, `32`,
  `34`, `38`, `39`) come only from the calculation. Reach them through the
  calculation, never by re-deriving the bracket, sum or percentage arithmetic.
- A strictly positive `04` with a zero base imponible previa (`13`) and no
  declared corrección explaining it, or a positive B2 tramo base (`61`/`64`)
  with a zero computed importe (`63`/`66`), is the under-declaration shape to
  question before export. Both are non-blocking advisories, legitimate in a
  loss-making period, so confirm rather than assume either way.
- Casilla `33` carries no guard at all (see above); this is a documented gap,
  not an oversight to route past silently.
- The modalidad and B1/B2 sub-lane are gated by data the person declares (INCN,
  which manual inputs are populated), never by the entity's legal form or size
  assumed from memory. Read which lane the calculated revision actually
  populated.
