---
name: cadrumo-preparar-modelo-353
description: >-
  Prepare a Modelo 353 (IVA grupo de entidades, modelo agregado) for the
  entidad dominante: create the work unit, calculate the group's monthly
  aggregate, check the member Modelo 322 coverage behind it, verify, write the
  local fichero-BOE once the person agrees, and leave the filing to the person.
  Use when the person's entity is the entidad dominante of an IVA grupo.
applies_when:
  profile_facts:
    - fact: iva.group_dominant_entity_enrolled
      match: is_true
---

# Prepare Modelo 353

Modelo 353 is the monthly aggregate self-assessment the entidad dominante of an
IVA grupo de entidades files for the group as a whole, under the régimen
especial del grupo de entidades (Orden EHA/3434/2007). Cadrumo computes the
aggregate; you run the steps and relay what comes back. Never compute a
casilla value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are the entidad-dominante precondition, the monthly (never
quarterly) cadence, and a cross-member reconciliation surface that checks the
aggregate against every member's Modelo 322. That surface is still evolving:
read "Cross-member reconciliation" below before relying on it.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The person's entity is the entidad dominante of an IVA grupo de entidades
  (régimen especial, Orden EHA/3434/2007 art. 2) filing the group's monthly
  aggregate. Check what the registry says for this profile with operation
  `overview.explain` (`aeat app overview explain 353 --year <YEAR>`):
  `applicable`, `verdict`, `rationale` and `profile_facts`. If the entity is a
  member filing only its own individual result, load
  `cadrumo-preparar-modelo-322` instead; that is a distinct work unit.
- The entidad dominante's own ledger for the calendar month is built and
  classified, with IVA categories applied: operation `ledger.check` (`aeat app
  ledger check`) and operation `ledger.ratios.validate` (`aeat app ledger
  ratios validate`). Both only read.
- You know the `filing_year` and the monthly `period` token. Modelo 353 is
  always monthly; the registry has one revision for periods up to January 2026
  and another from February 2026 (`02`-`12` of 2026).

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `353`, `filing_year` and `period` (`aeat app modelo describe 353 --year
   <YEAR> --period <PERIOD>` and `aeat app modelo casillas 353 --year <YEAR>
   --period <PERIOD>`). See `reference/casillas.md` for the orientation; the
   casilla set differs between the two revisions.
2. Tell the person you will create the Modelo 353 work unit for that month in
   their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 353 --year <YEAR> --period <PERIOD>`). Keep the
   work unit id it returns.
3. Tell the person you will save a new draft calculation, then calculate:
   operation `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). Enter a manual casilla only with a value the person gave
   you (`--casilla <casilla-id>=<decimal>` on the command line; the operation's
   input schema says where it goes). Read any warning notices and pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The values are the snapshot's
   `casilla_values`, its `result_summary` names the headline casilla, and each
   casilla's `legal_refs` and `source_refs` are in its `observations` (`aeat app
   modelo work observations --work-unit-id <work-unit-id>`).

## What Modelo 353 computes

Two groups of casillas can appear, depending on the revision. Read the casilla
list for the period to see which you have.

- **Group totals from the entidad dominante's own ledger** (only in the
  revision up to January 2026): `iva.repercutido.general`,
  `iva.repercutido.reducido`, `iva.repercutido.super-reducido`,
  `iva.soportado.interiores` and `iva.autorepercutido.intracomunitaria` are
  bound to the entidad dominante's classified ledger, and
  `iva.cuota-devengada-total`, `iva.cuota-deducible-total` and
  `iva.resultado-regimen-general` are computed from them.
- **Casilla `01`, "Resultado total (sumatorio del resultado de entidades)"**
  (both revisions): bound to the Modelo 322 results of the group's members.
  From February 2026 this is how the group result is built, with the
  compensation, deduction and result casillas (`02`, `08`, `09`, `03`, `04`,
  `05`) around it.

Report the casilla the revision's `result_summary` names as the result, and
label every other figure for what it is.

## Cross-member reconciliation - still evolving, check before relying on it

Modelo 353 declares three bound casillas (`iva.reconciliacion.devengada-322`,
`iva.reconciliacion.deducible-322`, `iva.reconciliacion.resultado-322`) that
the registry grounds as the sum, across every grupo member, of that member's
own Modelo 322 `iva.cuota-devengada-total`, `iva.cuota-deducible-total` and
`iva.resultado-regimen-general` for the same month. Casilla `01` rests on the
same member data. This cross-member aggregation is still evolving: do not
present its output as a confirmed group figure without checking that it
resolved from real member data.

- The aggregation only sums observations captured with a distinct grupo-member
  identity for that (322, year, month). If the entidad dominante's profile does
  not have every member's roster declared, or a member's Modelo 322 was never
  captured back with its member identity, the casillas resolve from whatever is
  on record, which may be a single filer's value, not the true group sum, or
  the calculation may raise a validation error rather than produce a group
  total.
- Before quoting a figure that rests on member data, read operation
  `modelo.work.dependencies` (`aeat app modelo work dependencies --modelo 353
  --year <YEAR> --period <PERIOD>`) and its `clean_state`: `clean`, `blockers`
  and, per dependency, `missing_member_nifs` and `unexpected_member_nifs`. A
  blocker `missing_expected_group_member_roster`,
  `incomplete_group_member_coverage` or `unexpected_group_member_source` means
  the figures do not yet reflect a complete, confirmed member set. Tell the
  person that gap rather than reporting the figure as settled; the blocker's
  message names the follow-up (declare the roster, capture the missing member's
  filing, or review an unexpected member).
- In the revision up to January 2026, never let a reconciliation casilla
  override or silently correct the totals computed from the entidad dominante's
  own ledger: the two are independent, and the reconciliation is a cross-check
  only as good as the member data behind it today.

## Success assertions

- The calculation raised no warning you have not passed on.
- Where the revision has ledger totals, they are consistent with the entidad
  dominante's declared IVA devengado less IVA deducible for the month. If an
  advisory says classified IVA lines were consumed by no casilla, tell the
  person and resolve it in the ledger before going on.
- Any figure that rests on member data is reported only alongside its
  `clean_state` verdict, never as a bare number.
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
