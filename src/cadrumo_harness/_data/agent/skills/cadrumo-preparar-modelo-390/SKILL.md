---
name: cadrumo-preparar-modelo-390
description: >-
  Prepare a Modelo 390 (IVA declaración-resumen anual) from the year's four
  quarterly Modelo 303s: create the work unit, calculate the annual summary,
  verify it reconciles against the four trimestrales, write the local
  fichero-BOE once the person agrees, and leave the filing to the person. Use
  when the person files their annual IVA summary declaration.
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [GENERAL, SIMPLIFICADO]
---

# Prepare Modelo 390

Modelo 390 is the annual IVA declaración-resumen: it does not compute a new IVA
result, it reconciles the year's ledger-derived annual totals against the sum of
the four quarterly Modelo 303 autoliquidaciones for the same `filing_year`.
Cadrumo computes and reconciles it; you run the steps and relay what comes
back. Never compute a casilla value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are the precondition (all four 303 quarters, not one) and the
verify step (an inter-modelo reconciliation gate, not just a completeness
check).

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The ledger for the full `filing_year` is built and classified, with IVA
  categories and prorrata applied across all four quarters: operation
  `ledger.check` (`aeat app ledger check`) and operation
  `ledger.ratios.validate` (`aeat app ledger ratios validate`). Both only read.
- **All four Modelo 303 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated.** Read each quarter's revision before
  starting the 390: operations `modelo.work.revision` and
  `modelo.work.revision_snapshot` (`aeat app modelo work revision
  --work-unit-id <work-unit-id of that quarter>`). Modelo 390 folds these four
  filings into its annual totals; a missing or stale quarter blocks
  verification (see below). Operation `modelo.work.dependencies` (`aeat app
  modelo work dependencies --modelo 390 --year <YEAR> --period 0A`) lists the
  filings the 390 depends on and a `clean_state` with `clean` and `blockers`.
- The `filing_year`. The period is always the annual token `0A`; Modelo 390 has
  no quarterly variant.

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `390`, `filing_year` and `period` `0A` (`aeat app modelo describe 390 --year
   <YEAR> --period 0A` and `aeat app modelo casillas 390 --year <YEAR> --period
   0A`).
2. Tell the person you will create the Modelo 390 work unit for that year in
   their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 390 --year <YEAR> --period 0A`). Keep the work
   unit id it returns.
3. Tell the person you will save a new draft calculation from their ledger and
   their four 303 filings, then calculate: operation `modelo.work.calculate`
   (`aeat app modelo work calculate <work-unit-id>`). Enter a manual casilla
   only with a value the person gave you (`--casilla <casilla-id>=<decimal>` on
   the command line; the operation's input schema says where it goes). Read any
   warning notices and pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The values are the snapshot's
   `casilla_values`; each casilla's `legal_refs` and `source_refs` are in its
   `observations` (`aeat app modelo work observations --work-unit-id
   <work-unit-id>`).

## What Modelo 390 adds over the quarterly pattern

- **Annual totals** are ledger-derived directly (`iva.anual.cuota-devengada-total`,
  `iva.anual.cuota-deducible-total`, `iva.anual.resultado-regimen-general`),
  the same repercutido/soportado/recargo/intracomunitaria shape as Modelo 303,
  summed over the whole year instead of one quarter.
- **Reconciliation casillas** (`iva.anual.reconciliacion.devengada-303`,
  `iva.anual.reconciliacion.deducible-303`,
  `iva.anual.reconciliacion.resultado-303`) pull the same three totals from the
  four Modelo 303 quarters via cross-modelo relations, independently of the
  ledger.
- **Casilla 79** (régimen simplificado, `iva.anual.reconciliacion.devengada-simplificado-303`)
  comes from the 4T Modelo 303's régimen simplificado summary (binding
  `modelo-390-m303-simplificado-79-total-cuota-resultante`), because régimen
  simplificado settles once a year in the 4T filing; it is not summed across
  quarters.
- **Casillas 97 and 662** (compensación pendiente) partition the year's IVA
  wallet compensación state across the four 303 quarters: casilla 97
  (`iva.anual.compensacion-ultimo-periodo-97`) is the amount to compensate
  carried from the last period of the year, and casilla 662
  (`iva.anual.compensacion-generada-ejercicio-no-97`) is compensación generated
  during the year outside that last-period amount.

## Success assertions

- The calculation raised no warning you have not passed on.
- The annual ledger-derived totals are consistent with the four quarters'
  declared IVA devengado/deducible. If an advisory says classified IVA lines
  were consumed by no casilla, tell the person and resolve it in the ledger
  before going on.
- Every value you report is quoted verbatim from the revision, with its
  grounding.

## Verify and hand off

5. Verify: operation `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft and records a
   verification report. Modelo 390 verification is a **blocking equality
   gate**: the ledger-derived annual cuota devengada, cuota deducible and
   resultado each must equal the corresponding total reconciled from the four
   303 quarters. A `blocking_rule` finding here means a quarter is missing,
   stale, or was recalculated after the 390 was created: re-check each 303
   quarter's revision before retrying, and never edit the 390 casilla to force a
   match. An advisory also checks that `iva.anual.resultado-liquidacion` equals
   `iva.anual.reconciliacion.resultados-liquidaciones`; a blank manual casilla
   that the year's results contradict surfaces there, so relay it. Read `completeness_status`
   (`complete`, `incomplete` or `blocked`), every entry of `findings` and
   `missing_required_casilla_ids`. The command exits `1` for `incomplete` and
   `blocked`; that is a verdict, not a crash. Do not export a `blocked`
   revision.
6. Say what you are about to do and wait for the person's go-ahead in the
   conversation: you will write a local fichero-BOE for the verified revision
   to a path in the conversation workspace; nothing goes to AEAT. Then
   export: operation `modelo.export` (`aeat app modelo export <work-unit-id>
   --output <path>`). The file is not official AEAT evidence and the return is
   not filed; the person uploads it themselves in the AEAT portal.
7. After the person says they have filed, tell them you will read the evidence
   AEAT holds (read only on the AEAT side) and compare it with the saved
   calculation, then run operation `modelo.reconcile.pull` (`aeat app modelo
   reconcile pull <work-unit-id>`). Relay the verdict and every difference
   verbatim.
