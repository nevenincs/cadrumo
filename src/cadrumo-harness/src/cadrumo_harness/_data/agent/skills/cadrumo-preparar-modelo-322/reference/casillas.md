# Modelo 322 casillas — orientation

The registry is the authority for the exact casilla set, numbering, legal
grounding, and formulas of the revision that applies to a given
`(year, period)`. Read it with
`aeat app modelo casillas 322 --year <YEAR> --period <PERIOD>` and treat
that output as canonical; this page is orientation only, so you know what
shape you are looking at. Never report a casilla value from this page —
report the value the CLI computes, with its `legal_refs`/`source_refs`.

## Régimen general individual (single revision, monthly, `2008-y-siguientes`)

Modelo 322 has one registry-modelled revision spanning 2008 onward, monthly
cadence only (period tokens `01`-`12`).

- **Cuota devengada, per tipo** — three bound casillas
  (`iva.repercutido.general` 21%, `iva.repercutido.reducido` 10%,
  `iva.repercutido.super-reducido` 4%), each ledger-derived from this
  member's own repercutido lines classified at that rate.
- **Cuota autorepercutida intracomunitaria** — one bound casilla
  (`iva.autorepercutido.intracomunitaria`) for inversión del sujeto pasivo on
  intra-community acquisitions (LIVA art. 84), ledger-derived.
- **Cuota deducible interiores** — one bound casilla
  (`iva.soportado.interiores`) summing this member's soportado lines across
  all three tipos on domestic operations, ledger-derived.
- **Cuota devengada total** — computed casilla
  (`iva.cuota-devengada-total`) summing the three repercutido casillas plus
  the autorepercutido casilla.
- **Cuota deducible total** — computed casilla
  (`iva.cuota-deducible-total`) summing the soportado casilla plus the
  autorepercutido casilla (the autorepercutido cuota is simultaneously
  devengada and deducible under the reverse-charge mechanism).
- **Resultado del régimen general individual** — computed casilla
  (`iva.resultado-regimen-general`), cuota devengada total minus cuota
  deducible total. This is THIS MEMBER's own result, not the group's.

## How to read it safely

- Every cuota casilla is `input_kind = "bound"`, resolved by the
  `ledger_iva_aggregation` source from the classified ledger — never a
  manual entry. If a cuota looks wrong, fix the ledger classification and
  re-calculate; do not edit a casilla to a number you prefer.
- The three total/result casillas are `input_kind = "computed"`; read them
  only from `aeat app modelo work calculate` / `work revision`, never by
  hand-summing the bound casillas yourself.
- A classified IVA line whose cuota no binding consumes is the
  under-declaration shape the unconsumed-declarable-IVA advisory exists to
  catch; act on it before export rather than assuming a silent zero.
- Modelo 322 has no prorrata, recargo de equivalencia, or régimen simplificado
  casillas modelled at this revision — those regimes are incompatible with
  grupo de entidades membership under Orden EHA/3434/2007, so their absence
  here is by design, not an omission.
- The individual `resultado-regimen-general` is one input among several the
  entidad dominante's Modelo 353 aggregates across every member for the same
  month. Do not treat it as, or report it as, the group's final
  ingreso/devolución outcome — that determination happens only inside the
  Modelo 353 work unit.
