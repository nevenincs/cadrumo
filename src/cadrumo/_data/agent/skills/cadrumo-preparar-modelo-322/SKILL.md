---
name: cadrumo-preparar-modelo-322
description: >-
  Prepare a Modelo 322 (IVA grupo de entidades, modelo individual) from a
  classified ledger: create the work unit, calculate the individual member's
  cuota, verify, export the fichero-BOE, and hand off for the taxpayer to
  file. Use when the taxpayer is a member entity of an IVA grupo de entidades
  (régimen especial del grupo de entidades) filing its own monthly individual
  self-assessment.
applies_when:
  profile_facts:
    - fact: iva.group_member_enrolled
      match: is_true
---

# Prepare Modelo 322

Modelo 322 is the monthly individual self-assessment each member entity of an
IVA grupo de entidades files for itself, under the régimen especial del grupo
de entidades (Orden EHA/3434/2007). The CLI computes the member's own cuota
from its classified ledger; you orchestrate and relay. Never compute a
casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the grupo-membership precondition, the monthly
(never quarterly) cadence, and the fact that Modelo 322 is NOT the group's
final settlement — it feeds the entidad dominante's Modelo 353 aggregate.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The taxpayer is a member entity of an IVA grupo de entidades (régimen
  especial, Orden EHA/3434/2007 art. 1) and files its OWN individual monthly
  self-assessment. If the taxpayer is not grupo-enrolled, route to
  `cadrumo-preparar-modelo-303` instead — Modelo 322 does not apply.
- The ledger for the calendar month is built and classified: IVA categories
  are applied (`aeat app ledger check`, `aeat app ledger ratios validate`).
- You know the `filing_year` and the monthly `period` token (`01`-`12`).
  Modelo 322 is always monthly, unlike the quarterly default for a
  non-grupo IVA filer.

## Procedure

1. Read the form shape: `aeat app modelo describe 322 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 322 --year <YEAR>
   --period <PERIOD>`.
2. Create the work unit: `aeat app modelo work create --modelo 322 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries `legal_refs`/
   `source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 322 adds over the quarterly IVA pattern

- **Monthly cadence, always** — Modelo 322 has no quarterly period tokens;
  every grupo member files every calendar month regardless of its size,
  because the régimen especial itself is a monthly regime (Orden
  EHA/3434/2007 art. 8).
- **Individual result only** — the calculated `iva.resultado-regimen-general`
  casilla is this member's OWN devengado-minus-deducible result. It is not
  the group's final ingreso/devolución outcome; the entidad dominante's
  Modelo 353 sums every member's Modelo 322 result for the same month to
  reach the group figure. Report the Modelo 322 result as this member's
  individual contribution, never as the group's final position.
- **No compensación or devolución decision at this level** — the individual
  Modelo 322 does not decide whether the group requests devolución or
  carries forward a saldo; that decision belongs to the Modelo 353 the
  entidad dominante files. Do not infer or state a group-level outcome from
  a single member's Modelo 322 calculation.

## The Modelo 322 → Modelo 353 relationship

Every grupo member files its own monthly Modelo 322 independently. The
entidad dominante then files Modelo 353 for the same month, which folds in
every member's Modelo 322 result casillas (cuota devengada, cuota deducible,
resultado del régimen general) via the registry's cross-member aggregation.
This aggregation surface is still evolving — do not assume the Modelo 353
aggregate has already picked up a freshly calculated Modelo 322 revision
without confirming via `aeat app modelo work revision` on the 353 work unit
itself. If you are preparing Modelo 353 for the entidad dominante, that is a
distinct work unit and outside this skill's scope; prepare each member's
Modelo 322 first, then read the Modelo 353 work unit's own calculated
revision to see what it consumed.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The individual result casilla is consistent with this member's declared
  IVA devengado less IVA deducible for the month; act on any
  unconsumed-declarable-IVA advisory the CLI surfaces.
- Every reported value is quoted verbatim from the JSON with its grounding.
- Never state the group's aggregate ingreso/devolución outcome from this
  work unit — that figure belongs to the entidad dominante's Modelo 353.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
