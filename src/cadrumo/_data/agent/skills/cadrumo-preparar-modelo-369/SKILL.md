---
name: cadrumo-preparar-modelo-369
description: >-
  Prepare a Modelo 369 (IVA regímenes especiales OSS / IOSS ventanilla única)
  from a classified ledger: create the work unit, calculate the cuota for the
  applicable esquema, verify, export the fichero-BOE, and hand off for the
  taxpayer to file. Use when the taxpayer is OSS/IOSS-enrolled and sells
  cross-border B2C goods or services to consumers in other EU member states.
applies_when:
  profile_facts:
    - fact: iva.oss_enrolled
      match: is_true
---

# Prepare Modelo 369

Modelo 369 is the IVA one-stop-shop (ventanilla única) self-assessment for
cross-border B2C supplies. The CLI computes the cuota per destination member
state from the classified ledger; you orchestrate and relay. Never compute a
casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the OSS-enrolment precondition, the choice of esquema
(three distinct schemes with three distinct period-token grammars, all under
modelo id `369`), and the per-destination-member-state casilla shape.

## The three esquemas — pick one by period token, not by a separate command

Modelo 369 has three registry-modelled schemes, each with its own filing
cadence and period-token grammar. `--modelo 369` is always the same; the
esquema is selected implicitly by the `--period` token you pass:

- **Esquema Unión** — intra-EU distance sales of goods, electronic-interface-
  facilitated supplies, and services from an EU-established taxable person to
  consumers in other member states (LIVA art. 163 unvicies-quatervicies).
  Quarterly: `--period 1T`, `2T`, `3T`, `4T`.
- **Esquema Exterior** — services from a non-EU-established taxable person to
  EU consumers (LIVA art. 163 octiesdecies-vicies). Quarterly with a distinct
  token family: `--period EXT-1T`, `EXT-2T`, `EXT-3T`, `EXT-4T`.
- **Esquema Importación (IOSS)** — distance sales of imported goods with
  intrinsic value ≤ 150 EUR (LIVA art. 163 quinvicies-octovicies). Monthly:
  `--period 01` through `12`.

Confirm which esquema applies to the taxpayer's activity before creating the
work unit — a sujeto pasivo can be enrolled in more than one esquema
simultaneously (e.g. an EU-established seller with imported low-value goods
files both Unión and Importación), each on its own cadence, as independent
work units.

## Preconditions

- An active profile exists and is **OSS/IOSS-enrolled**:
  `aeat app overview status` reports `iva.oss_enrolled = true`. Modelo 369
  applies only to B2C cross-border supplies to consumers in other member
  states; intracommunity B2B operations between taxable persons are declared
  in Modelo 303/349 instead, never in Modelo 369. If `oss_enrolled` is false,
  stop and route to the profile role — do not create the work unit.
- The ledger for the period is built and classified: IVA categories are
  applied so cross-border B2C invoices carry an OSS/IOSS transaction kind
  (`aeat app ledger check`). The classification is derived from invoice facts
  (customer residency, customer tax status, destination member state) — you
  never set the esquema or destination member state by hand.
- You know the `filing_year` and the `period` token for the esquema you are
  preparing (see above).

## Procedure

1. Read the form shape: `aeat app modelo describe 369 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 369 --year <YEAR>
   --period <PERIOD>`. The casilla set returned is scoped to the esquema your
   `--period` token selects.
2. Create the work unit: `aeat app modelo work create --modelo 369 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries `legal_refs`/
   `source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 369 adds over the quarterly IVA pattern

- **Per-destination-member-state cuota casillas** — each esquema declares one
  bound casilla per (destination member state, supply kind) pair (e.g. cuota
  IVA al destino DE por servicios, cuota al destino FR por servicios), each
  independently ledger-derived via the `ledger_oss_aggregation` source. Do
  not sum member states yourself; the registry's total casilla does that.
- **A single total casilla per esquema** — `iva.union.cuota-total`,
  `iva.exterior.cuota-total`, or `iva.importacion.cuota-total` sums every
  destination-member-state cuota casilla for that esquema via a registry
  formula. Read the total from the calculated revision, never by hand-adding
  the per-destination rows.
- **No cross-esquema total** — each esquema's work unit is independently
  calculated and verified; there is no Modelo-369-wide combined casilla
  across Unión, Exterior, and Importación.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- Every reported per-destination cuota and the esquema total are consistent
  with the classified ledger's OSS/IOSS-tagged issued invoices for that
  member state; act on any unconsumed-declarable-IVA advisory the CLI
  surfaces (a classified OSS/IOSS invoice whose cuota no binding consumed).
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
