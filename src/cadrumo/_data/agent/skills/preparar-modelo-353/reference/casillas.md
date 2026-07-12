# Modelo 353 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 353 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what
shape you are looking at. Never report a casilla value from this page —
report the value the CLI computes, with its `legal_refs`/`source_refs`.

## Régimen general agregado (single revision, monthly, `2008-y-siguientes`)

Modelo 353 has one registry-modelled revision spanning 2008 onward, monthly
cadence only (period tokens `01`-`12`).

### Directly-computed group casillas

- **Cuota devengada, per tipo** — three bound casillas
  (`iva.repercutido.general` 21%, `iva.repercutido.reducido` 10%,
  `iva.repercutido.super-reducido` 4%), ledger-derived from the entidad
  dominante's own repercutido lines classified at that rate.
- **Cuota autorepercutida intracomunitaria** — one bound casilla
  (`iva.autorepercutido.intracomunitaria`) for inversión del sujeto pasivo
  on intra-community acquisitions (LIVA art. 84), ledger-derived.
- **Cuota deducible interiores** — one bound casilla
  (`iva.soportado.interiores`) summing the entidad dominante's soportado
  lines across all three tipos on domestic operations, ledger-derived.
- **Cuota devengada total** — computed casilla
  (`iva.cuota-devengada-total`) summing the three repercutido casillas plus
  the autorepercutido casilla.
- **Cuota deducible total** — computed casilla
  (`iva.cuota-deducible-total`) summing the soportado casilla plus the
  autorepercutido casilla.
- **Resultado del régimen general** — computed casilla
  (`iva.resultado-regimen-general`), cuota devengada total minus cuota
  deducible total. These eight casillas are what the group files; report
  them as the group's aggregate position.

### Cross-member reconciliation casillas (still evolving)

- **`iva.reconciliacion.devengada-322`**, **`iva.reconciliacion.deducible-322`**,
  **`iva.reconciliacion.resultado-322`** — bound casillas grounded as the
  `per_grupo_member` sum, across every grupo member, of that member's own
  Modelo 322 `iva.cuota-devengada-total` / `iva.cuota-deducible-total` /
  `iva.resultado-regimen-general` for the same month. They are part of the
  registry's completeness manifest for this revision, so `aeat app modelo
  casillas 353` always lists them, but their VALUE is only as trustworthy
  as the member-observation history behind it — see the "Cross-member
  reconciliation" section in `SKILL.md` before quoting one. Do not confuse
  these with the directly-computed group casillas above: the reconciliation
  is a cross-check, not an alternate way to compute the filing.

## How to read it safely

- Every directly-computed cuota casilla is `input_kind = "bound"`, resolved
  by the `ledger_iva_aggregation` source from the entidad dominante's
  classified ledger — never a manual entry. If a cuota looks wrong, fix the
  ledger classification and re-calculate; do not edit a casilla to a number
  you prefer.
- The total/result casillas are `input_kind = "computed"`; read them only
  from `aeat app modelo work calculate` / `work revision`, never by
  hand-summing the bound casillas yourself.
- The three reconciliation casillas are also `input_kind = "bound"`, but
  their source is the cross-member `previous_filing` fan-in over captured
  Modelo 322 observations, not the entidad dominante's own ledger. Run
  `aeat app modelo work dependencies --modelo 353 --year <YEAR> --period
  <PERIOD>` and read its clean-state payload before treating a
  reconciliation figure as a confirmed group cross-check.
- A classified IVA line whose cuota no binding consumes is the
  under-declaration shape the unconsumed-declarable-IVA advisory exists to
  catch; act on it before export rather than assuming a silent zero.
- Modelo 353 has no prorrata, recargo de equivalencia, or régimen
  simplificado casillas modelled at this revision — those regimes are
  incompatible with grupo de entidades membership under Orden
  EHA/3434/2007, so their absence here is by design, not an omission.
