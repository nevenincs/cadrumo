---
name: cadrumo-preparar-modelo-303
description: >-
  Prepare a Modelo 303 (IVA autoliquidación) from the classified ledger: create
  the work unit, calculate, verify, write the local fichero-BOE once the person
  agrees, and leave the filing to the person. Use when the person wants their
  periodic (quarterly or monthly) IVA return prepared.
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [GENERAL, SIMPLIFICADO]
---

# Prepare Modelo 303

Modelo 303 is the periodic IVA self-assessment. Cadrumo computes the IVA result
from the classified ledger; you run the steps and relay what comes back. Never
compute a casilla value yourself.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Preconditions

- `status` reports a session that admits this server; you work only inside that
  profile.
- The ledger for the period is built and classified, with IVA categories and
  prorrata applied: operation `ledger.check` (`aeat app ledger check`) and
  operation `ledger.ratios.validate` (`aeat app ledger ratios validate`). Both
  only read.
- You know the `filing_year` and the `period` (`1T`-`4T`, or a monthly token
  `01`-`12`).

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `303`, `filing_year` and `period` (`aeat app modelo describe 303 --year
   <YEAR> --period <PERIOD>` and `aeat app modelo casillas 303 --year <YEAR>
   --period <PERIOD>`).
2. Tell the person you will create the Modelo 303 work unit for that year and
   period in their profile, then create it: operation `modelo.work.create`
   (`aeat app modelo work create --modelo 303 --year <YEAR> --period
   <PERIOD>`). Keep the work unit id it returns.
3. Tell the person you will save a new draft calculation from their ledger,
   then calculate: operation `modelo.work.calculate` (`aeat app modelo work
   calculate <work-unit-id>`). Enter a manual casilla only with a value the
   person gave you (`--casilla <casilla-id>=<decimal>` on the command line; the
   operation's input schema says where it goes). Read any warning notices and
   pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The values are the snapshot's
   `casilla_values`; each casilla's `legal_refs` and `source_refs` are in its
   `observations` (`aeat app modelo work observations --work-unit-id
   <work-unit-id>`).

## Compensación pendiente (the IVA wallet carry-forward)

When a quarter's IVA deducible exceeds IVA devengado, the excess does not
vanish: LIVA arts. 99 and 115-116 let it carry forward and offset a future
quarter's cuota instead of being refunded immediately. The registry models
this as four casillas per quarter, chained across periods:

- **Casilla 110** (`iva.compensacion-pendiente-periodos-anteriores`) - the
  balance carried IN from the prior quarter's
  `iva.compensacion-disponible-fin-periodo` (its casilla 87 plus the compensation
  that quarter generated), resolved as a `previous_filing` binding
  (`modelo-303-compensacion-pendiente-anteriores`).
  Never enter this by hand; it is bound.
- **Casilla 78** (`iva.compensacion-aplicada-periodo`) - the portion of
  casilla 110 actually applied against this quarter's resultado, computed by
  the registry formula.
- **Casilla 87** (`iva.compensacion-pendiente-periodos-posteriores`) - the
  remaining balance carried OUT to the next quarter's casilla 110.
- **Casilla 69** (`iva.resultado`) - the quarter's resultado
  (`[66]+[77]+[68]-[78]`), so a nonzero casilla 78 reduces what would
  otherwise be payable.

Read the revision and confirm casilla 110 matches the prior quarter's casilla
87 before treating a quarter as ready to verify; a mismatch means the prior
quarter was recalculated after this one was created, and this quarter must be
recreated against the current chain. The first quarter of a filing_year (or a
taxpayer's first-ever 303) carries casilla 110 = 0. Never override casilla 110
or 87 to force a balance; the chain is registry-computed end to end.

## Success assertions

- The calculation raised no warning you have not passed on.
- The IVA result casilla is consistent with the declared IVA devengado less IVA
  deducible. If an advisory says classified IVA lines were consumed by no
  casilla, tell the person and resolve it in the ledger before going on.
- If casilla 87 (or 110) is nonzero, the next quarter's work unit must reflect
  it before that quarter is verified.
- Every value you report is quoted verbatim from the revision, with its
  grounding.

## Verify and hand off

5. Verify: operation `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft and records a
   verification report. Read `completeness_status` (`complete`, `incomplete` or
   `blocked`), every entry of `findings` (advisories included) and
   `missing_required_casilla_ids`. The command exits `1` for `incomplete` and
   `blocked`; that is a verdict, not a crash. Do not export a `blocked`
   revision.
6. Before exporting, ask the person three things this export carries, and use
   what they answer: what to do with a negative result (`--refund-election`
   `compensar` or `devolver`), how a positive result is paid
   (`--payment-election` `ingreso`, `domiciliacion` or `cuenta_corriente`), and
   whether an earlier domiciliación is kept (`--prior-domiciliation-election`
   `keep` or `cancel_or_modify`). The export operation's request carries the
   same three elections.
7. Say what you are about to do and wait for the person's go-ahead in the
   conversation: you will write a local fichero-BOE for the verified revision
   to a path in the conversation workspace; nothing goes to AEAT. Then
   export: operation `modelo.export` (`aeat app modelo export <work-unit-id>
   --output <path>`). The file is not official AEAT evidence and the return is
   not filed; the person uploads it themselves in the AEAT portal.
8. After the person says they have filed, tell them you will read the evidence
   AEAT holds (read only on the AEAT side) and compare it with the saved
   calculation, then run operation `modelo.reconcile.pull` (`aeat app modelo
   reconcile pull <work-unit-id>`). Relay the verdict and every difference
   verbatim.
