# Modelo 353 casillas - orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with tool `authority`, `query` `casillas`, `modelo`
`353`, `filing_year` and `period` (`aeat app modelo casillas 353 --year <YEAR>
--period <PERIOD>`), and treat that output as canonical. This page is
orientation only, so you know what shape you are looking at. Never report a
casilla value from this page: report the value the calculation produced, with
its `legal_refs` and `source_refs`.

Modelo 353 is monthly only (period tokens `01`-`12`). The registry has two
revisions: `2021-hasta-2026-01` (every period up to January 2026) and
`2026-desde-02` (`02`-`12` of 2026). They share a core and differ in the
ledger totals.

## Core of both revisions

- `01` - Resultado total (sumatorio del resultado de entidades). Bound to the
  Modelo 322 results of the group's members.
- `02` - Cuotas a compensar pendientes de ejercicios anteriores (manual).
- `08` - Cuotas a compensar de periodos anteriores aplicadas en este periodo
  (manual).
- `09` - Cuotas a compensar pendientes para periodos posteriores (computed).
- `03` - Resultado, `[01] - [08]` (computed).
- `04` - A deducir: resultado de autoliquidaciones anteriores del mismo
  concepto (manual).
- `05` - Resultado de la autoliquidación, `[03] - [04]` (computed).
- `06` - Importe a compensar and `07` - Importe a devolver (manual), and
  `papel.importe-ingreso` (manual).
- The three reconciliation casillas, below.

The revision from February 2026 also lists casilla `10`, "Pago a cuenta de
entregas de gasolinas, gasóleos y biocarburantes" (manual).

## Ledger totals (revision up to January 2026 only)

These come from the entidad dominante's own classified ledger and are labelled
as the group aggregate:

- Cuota devengada, per tipo - three bound casillas (`iva.repercutido.general`
  21%, `iva.repercutido.reducido` 10%, `iva.repercutido.super-reducido` 4%).
- `iva.autorepercutido.intracomunitaria` - cuota autorepercutida on
  intra-community acquisitions (LIVA art. 84), bound.
- `iva.soportado.interiores` - cuota deducible on domestic operations, bound.
- `iva.cuota-devengada-total`, `iva.cuota-deducible-total` and
  `iva.resultado-regimen-general` - computed totals and the group result
  (cuota devengada agregada menos cuota deducible agregada).

The revision from February 2026 does not list these casillas.

## Cross-member reconciliation casillas (still evolving)

- `iva.reconciliacion.devengada-322`, `iva.reconciliacion.deducible-322` and
  `iva.reconciliacion.resultado-322` - bound casillas grounded as the sum,
  across every grupo member, of that member's own Modelo 322
  `iva.cuota-devengada-total`, `iva.cuota-deducible-total` and
  `iva.resultado-regimen-general` for the same month. `aeat app modelo
  casillas 353` always lists them, but their value is only as trustworthy as
  the member-observation history behind it. See the "Cross-member
  reconciliation" section in `SKILL.md` before quoting one.
- Do not confuse them with the ledger totals above: the reconciliation is a
  cross-check, not an alternate way to compute the filing.

## How to read it safely

- A bound casilla is never a manual entry. If a ledger cuota looks wrong, fix
  the ledger classification and calculate again; do not edit a casilla to a
  number you prefer.
- Computed casillas come only from the calculation. Read them from the
  revision, never by hand-summing other casillas yourself.
- The casillas that rest on member Modelo 322 results (`01`, the three
  reconciliation casillas) are checked with operation
  `modelo.work.dependencies` (`aeat app modelo work dependencies --modelo 353
  --year <YEAR> --period <PERIOD>`); read its `clean_state` before treating
  one as a confirmed group figure.
- A classified IVA line whose cuota no binding consumes is the
  under-declaration shape the advisory about IVA consumed by no casilla exists
  to catch. Act on it before export rather than assuming a silent zero.
