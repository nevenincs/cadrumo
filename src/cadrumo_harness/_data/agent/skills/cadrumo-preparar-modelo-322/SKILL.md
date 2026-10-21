---
name: cadrumo-preparar-modelo-322
description: >-
  Prepare a Modelo 322 (IVA grupo de entidades, modelo individual) from the
  classified ledger: create the work unit, calculate the member's own monthly
  result, verify, write the local fichero-BOE once the person agrees, and leave
  the filing to the person. Use when the person's entity is a member of an IVA
  grupo de entidades filing its own monthly individual return.
applies_when:
  profile_facts:
    - fact: iva.group_member_enrolled
      match: is_true
---

# Prepare Modelo 322

Modelo 322 is the monthly individual self-assessment each member entity of an
IVA grupo de entidades files for itself, under the régimen especial del grupo
de entidades (Orden EHA/3434/2007). Cadrumo computes the member's own result
from its classified ledger; you run the steps and relay what comes back. Never
compute a casilla value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are the grupo-membership precondition, the monthly (never
quarterly) cadence, and the fact that Modelo 322 is NOT the group's final
settlement: it feeds the entidad dominante's Modelo 353.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The person's entity is a member of an IVA grupo de entidades (régimen
  especial, Orden EHA/3434/2007 art. 1) and files its OWN individual monthly
  self-assessment. Check what the registry says for this profile with
  operation `overview.explain` (`aeat app overview explain 322 --year <YEAR>`):
  `applicable`, `verdict`, `rationale` and `profile_facts`. If the entity is
  not grupo-enrolled, load `cadrumo-preparar-modelo-303` instead; Modelo 322
  does not apply.
- The ledger for the calendar month is built and classified, with IVA
  categories applied: operation `ledger.check` (`aeat app ledger check`) and
  operation `ledger.ratios.validate` (`aeat app ledger ratios validate`). Both
  only read.
- You know the `filing_year` and the monthly `period` token (`01`-`12`).
  Modelo 322 is always monthly, unlike the quarterly default for a non-grupo
  IVA filer.

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `322`, `filing_year` and `period` (`aeat app modelo describe 322 --year
   <YEAR> --period <PERIOD>` and `aeat app modelo casillas 322 --year <YEAR>
   --period <PERIOD>`). See `reference/casillas.md` for the orientation.
2. Tell the person you will create the Modelo 322 work unit for that month in
   their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 322 --year <YEAR> --period <PERIOD>`). Keep the
   work unit id it returns.
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

## What Modelo 322 adds over the quarterly IVA pattern

- **Monthly cadence, always.** Modelo 322 has no quarterly period tokens; every
  grupo member files every calendar month regardless of its size, because the
  régimen especial itself is a monthly regime (Orden EHA/3434/2007 art. 8).
- **Individual result only.** The calculated `iva.resultado-regimen-general`
  casilla is this member's OWN devengado-minus-deducible result. It is not the
  group's final ingreso/devolución outcome; the entidad dominante's Modelo 353
  brings together every member's Modelo 322 result for the same month to reach
  the group figure. Report the Modelo 322 result as this member's individual
  contribution, never as the group's final position.
- **No compensación or devolución decision at this level.** The individual
  Modelo 322 does not decide whether the group requests devolución or carries
  forward a saldo; that decision belongs to the Modelo 353 the entidad
  dominante files. Do not infer or state a group-level outcome from a single
  member's Modelo 322 calculation.

## The Modelo 322 and Modelo 353 relationship

Every grupo member files its own monthly Modelo 322 independently. The entidad
dominante then files Modelo 353 for the same month, which takes in every
member's Modelo 322 result through the registry's cross-member aggregation.
This aggregation surface is still evolving: do not assume the Modelo 353 has
already picked up a freshly calculated Modelo 322 revision without reading the
revision of the Modelo 353 work unit itself. Preparing the Modelo 353 for the
entidad dominante is a distinct work unit; load `cadrumo-preparar-modelo-353`
for it. Prepare each member's Modelo 322 first, then read the Modelo 353 work
unit's own calculated revision to see what it consumed.

## Success assertions

- The calculation raised no warning you have not passed on.
- The individual result casilla is consistent with this member's declared IVA
  devengado less IVA deducible for the month. If an advisory says classified
  IVA lines were consumed by no casilla, tell the person and resolve it in the
  ledger before going on.
- Every value you report is quoted verbatim from the revision, with its
  grounding.
- Never state the group's aggregate ingreso/devolución outcome from this work
  unit; that figure belongs to the entidad dominante's Modelo 353.

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
