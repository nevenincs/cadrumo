---
name: cadrumo-preparar-modelo-353
description: >-
  Prepare a Modelo 353 (IVA grupo de entidades, modelo agregado) from the
  entidad dominante's own classified ledger: create the work unit, calculate
  the group's aggregated IVA result, verify, export the fichero-BOE, and hand
  off for the taxpayer to file. Use when the taxpayer is the entidad
  dominante of an IVA grupo de entidades filing the group's monthly
  aggregate self-assessment.
applies_when:
  profile_facts:
    - fact: iva.group_dominant_entity_enrolled
      match: is_true
---

# Prepare Modelo 353

Modelo 353 is the monthly aggregate self-assessment the entidad dominante of
an IVA grupo de entidades files for the group as a whole, under the régimen
especial del grupo de entidades (Orden EHA/3434/2007). The CLI computes the
group's own aggregate cuota from the entidad dominante's classified ledger;
you orchestrate and relay. Never compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the entidad-dominante precondition, the monthly
(never quarterly) cadence, and a second, still-evolving reconciliation
surface that cross-checks the aggregate against every member's Modelo 322 —
read the "Cross-member reconciliation" section below before relying on it.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The taxpayer is the entidad dominante of an IVA grupo de entidades
  (régimen especial, Orden EHA/3434/2007 art. 2) filing the group's monthly
  aggregate self-assessment. If the taxpayer is a member entity filing only
  its own individual result, route to `cadrumo-preparar-modelo-322` instead — that
  is a distinct work unit and outside this skill's scope.
- The entidad dominante's own ledger for the calendar month is built and
  classified: IVA categories are applied (`aeat app ledger check`,
  `aeat app ledger ratios validate`).
- You know the `filing_year` and the monthly `period` token (`01`-`12`).
  Modelo 353 is always monthly.

## Procedure

1. Read the form shape: `aeat app modelo describe 353 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 353 --year <YEAR>
   --period <PERIOD>`.
2. Create the work unit: `aeat app modelo work create --modelo 353 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries `legal_refs`/
   `source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 353 computes directly

- **Cuota devengada / deducible per tipo, autorepercutido, and the two
  totals plus resultado** (`iva.repercutido.general`,
  `iva.repercutido.reducido`, `iva.repercutido.super-reducido`,
  `iva.soportado.interiores`, `iva.autorepercutido.intracomunitaria`,
  `iva.cuota-devengada-total`, `iva.cuota-deducible-total`,
  `iva.resultado-regimen-general`) are `ledger_iva_aggregation`-bound
  casillas resolved directly from the entidad dominante's own classified
  ledger, the same shape as Modelo 303/322. These are the casillas the
  filing result is built from; report them as the group's aggregate
  position.

## Cross-member reconciliation — still evolving, verify before relying on it

Modelo 353 also declares three additional bound casillas
(`iva.reconciliacion.devengada-322`, `iva.reconciliacion.deducible-322`,
`iva.reconciliacion.resultado-322`) that the registry grounds as the sum,
across every grupo member, of that member's own Modelo 322
`iva.cuota-devengada-total` / `iva.cuota-deducible-total` /
`iva.resultado-regimen-general` for the same month. This is a
**cross-member aggregation surface that is still evolving** — do not
present its output as a confirmed group cross-check without verifying it
resolved from real member data:

- The reconciliation only sums observations that were captured with a
  distinct grupo-member identity for that (322, year, month). If the
  entidad dominante's profile does not have every member's roster declared,
  or a member's Modelo 322 was never captured back into observation
  history with its member identity, the reconciliation casillas will
  resolve from whatever is on record — which may be a single filer's value,
  not the true group sum — or the calculation may raise a validation error
  rather than silently produce the group total.
- Before quoting a reconciliation casilla as validated, run
  `aeat app modelo work dependencies --modelo 353 --year <YEAR> --period
  <PERIOD>` and read the `clean_state` payload. A
  `MISSING_EXPECTED_GROUP_MEMBER_ROSTER`, `INCOMPLETE_GROUP_MEMBER_COVERAGE`,
  or `UNEXPECTED_GROUP_MEMBER_SOURCE` blocker means the reconciliation
  casillas do not yet reflect a complete, confirmed member set — surface
  that gap to the operator rather than reporting the figure as settled.
  Every blocker's message names the concrete follow-up (configure the
  roster, capture the missing member's filing, or review an unexpected
  member).
- Never let a reconciliation casilla override or silently correct the
  directly-computed `iva.cuota-devengada-total` /
  `iva.cuota-deducible-total` / `iva.resultado-regimen-general` casillas
  above. The two surfaces are independent: the first is what the group
  files; the reconciliation is a cross-check that is only as good as the
  member data captured behind it today.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The directly-computed group result casillas are consistent with the
  entidad dominante's declared IVA devengado less IVA deducible for the
  month; act on any unconsumed-declarable-IVA advisory the CLI surfaces.
- Any cross-member reconciliation figure is reported only alongside its
  `work dependencies` clean-state status, never as a bare number.
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id>
   --format json`. Treat exit `1` as a verdict; do not export a BLOCKED
   revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
