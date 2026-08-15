# Modelo 200 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 200 --year <YEAR> --period 0A` and treat that output
as canonical; this page is orientation only, so you know which section a
casilla belongs to and where to look. Never report a casilla value from this
page - report the value the CLI computes, with its `legal_refs`/`source_refs`.
Because Modelo 200 spans hundreds of casillas across many páginas of the
official form, always scope the read to the section the taxpayer's question
concerns rather than reading the whole set.

## The section map

Modelo 200 groups its casillas into páginas that mirror the AEAT paper form
(Diseño de Registros DP200012 through DP200020D and beyond). The load-bearing
groups an operator navigates:

- **Identificación y caracteres de la declaración** — entity identification,
  `legal_entity_form`, régimen fiscal flags (entidad parcialmente exenta,
  incentivos de entidad de reducida dimensión, entidad de nueva creación).
  Profile-sourced; feeds the tipo de gravamen dispatch downstream.
- **Balance y cuenta de pérdidas y ganancias** — the entity's finalised
  cuentas anuales, entered manually. Casilla `00500` (resultado after IS) and
  casilla `00501` (resultado before IS, the fiscal-base starting point) live
  here. These are the two earliest links in the base-determination chain -
  see `no-silent-under-declaration` for the guard on this handoff.
- **Liquidación I — resultado de la cuenta de pérdidas y ganancias** — carries
  `00501` forward into the fiscal computation.
- **Liquidación III — base imponible** — ajustes extracontables (aumentos y
  disminuciones), reservas de capitalización/nivelación, compensación de
  bases imponibles negativas (`DP200014:00547`, capped BLOCKING by both the
  art. 26.1 ceiling and the opening BIN stock), and the resulting base
  imponible (`DP200014:00552`) and tipo de gravamen (`DP200014:00558`).
- **Cuota íntegra / Liquidación IV — otras deducciones** — cuota íntegra
  (`DP200014:00562`) via bracket application on the base and rate, then
  deducciones (doble imposición internacional and interna, incentivos de
  entidad de reducida dimensión) down to cuota líquida
  (`DP200014B:00592`).
- **Detalle compensación bases imponibles negativas — TOTAL** — the BIN stock
  ledger: opening pending (`00670`), applied this period
  (`DP200014:00547`), and closing pending for future periods (`00671`, which
  should reconcile against the roll-forward - see the continuity advisory).
- **Dotaciones por deterioro de créditos (art. 13)** — cross-year carried
  stock split by condition-state (`01494`/`01495` opening,
  `01498`/`01499` closing); only the "cumplido" (condition-met) stock may be
  integrated this period, and a positive cumplido stock with a zero amount
  integrated (`01496`) is a non-blocking advisory.
- **Pagos a cuenta / pagos fraccionados** — the year's Modelo 202 instalments
  (casillas `34` and `03` on the source 202, mutually exclusive modalidades)
  folded in as a credit against the cuota diferencial.
- **Liquidación — resultado de la declaración** — the final amount to pay or
  to be refunded.

## How to read it safely

- Inputs fall into three provenance classes and each is fixed differently:
  manually-entered accounting facts with no ledger counterpart (`00500`,
  `00501`, most ajustes, deducciones — route to the role that owns
  operator-entered facts), profile-sourced (`legal_entity_form`, INCN,
  new-entity flag — fix the profile), and cross-modelo folded-in
  (Modelo 202 instalments — fix the source 202 filing and recalculate).
  Never edit a casilla to a number you prefer regardless of provenance.
- Computed casillas (base imponible, tipo de gravamen, cuota íntegra, cuota
  líquida, and the resultado) come only from `aeat app modelo work
  calculate`. Reach them through the calculation, never by re-deriving the
  bracket or dispatch arithmetic.
- A strictly positive `00500` with a zero `00501`, or a strictly positive
  `00501` with a zero base imponible (`DP200014:00552`) and no declared
  ajuste/BIN compensation/corrección explaining it, is the under-declaration
  shape to question before any export (see `cadrumo-operator-grounding` and
  `cadrumo-operator-safety-handoff`). It is legitimate for a loss-making year or a
  year with full BIN compensation, so confirm rather than assume either way.
- The BIN compensation applied (`DP200014:00547`) is BLOCKING-capped by both
  the art. 26.1 elective ceiling and the opening stock (`00670`) - a verify
  finding here means the applied amount must be corrected, never overridden.
  The BIN closing-stock continuity check (`00671` against the roll-forward)
  is advisory, not blocking.
- The tipo de gravamen depends on entity form, INCN, and the new-entity flag
  together - never assume a rate (25%, the micro-empresa two-tranche
  schedule, the ERD art. 101 schedule, or a special-regime rate) from the
  entity's legal form alone. Read the calculated `DP200014:00558` /
  `DP200014:00562` pair from the revision.
- The Modelo 202 pagos-fraccionados fold-in is revision-stamped; if a source
  instalment's value cannot be confirmed, surface the shortfall rather than
  trusting a silent zero credit.
