---
name: cadrumo-preparar-modelo-369
description: >-
  Prepare a Modelo 369 (IVA regímenes especiales OSS / IOSS ventanilla única)
  from the classified ledger: pick the esquema from the period token, create
  the work unit, calculate, verify, write the local fichero-BOE once the person
  agrees, and leave the filing to the person. Use when the person is OSS/IOSS
  enrolled and sells cross-border to consumers in other EU member states.
applies_when:
  profile_facts:
    - fact: iva.oss_enrolled
      match: is_true
---

# Prepare Modelo 369

Modelo 369 is the IVA one-stop-shop (ventanilla única) self-assessment for
cross-border B2C supplies. Cadrumo computes the cuota from the classified
ledger; you run the steps and relay what comes back. Never compute a casilla
value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are the OSS-enrolment precondition, the choice of esquema (three
distinct schemes with three distinct period-token grammars, all under modelo
id `369`), and the casilla shape described below.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## The three esquemas - pick one by period token, not by a separate command

Modelo 369 has three registry-modelled schemes, each with its own filing
cadence and period-token grammar. The modelo is always `369`; the esquema is
selected by the period token you pass:

- **Esquema Unión** - intra-EU distance sales of goods, electronic-interface-
  facilitated supplies, and services from an EU-established taxable person to
  consumers in other member states (LIVA art. 163 unvicies-quatervicies).
  Quarterly: period `1T`, `2T`, `3T`, `4T`.
- **Esquema Exterior** - services from a non-EU-established taxable person to
  EU consumers (LIVA art. 163 octiesdecies-vicies). Quarterly with a distinct
  token family: period `EXT-1T`, `EXT-2T`, `EXT-3T`, `EXT-4T`.
- **Esquema Importación (IOSS)** - distance sales of imported goods with
  intrinsic value of 150 EUR or less (LIVA art. 163 quinvicies-octovicies).
  Monthly: period `01` through `12`.

Confirm which esquema applies to the person's activity before creating the work
unit. A sujeto pasivo can be enrolled in more than one esquema at once (for
example an EU-established seller with imported low-value goods files both Unión
and Importación), each on its own cadence, as independent work units.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The profile is **OSS/IOSS-enrolled**. Check it with operation
  `overview.explain` (`aeat app overview explain 369 --year <YEAR>`):
  `applicable`, `verdict`, `rationale` and `profile_facts` (`iva.oss_enrolled`).
  Modelo 369 applies only to B2C cross-border supplies to consumers in other
  member states; intracommunity B2B operations between taxable persons are
  declared in Modelo 303/349 instead, never in Modelo 369. If the profile is not
  OSS/IOSS-enrolled, stop and tell the person; do not create the work unit.
- The ledger for the period is built and classified, with IVA categories
  applied so cross-border B2C invoices carry an OSS/IOSS transaction kind:
  operation `ledger.check` (`aeat app ledger check`) reads the ledger and
  reports anomalies. The classification is derived from invoice facts (customer
  residency, customer tax status, destination member state); you never set the
  esquema or destination member state by hand.
- You know the `filing_year` and the `period` token for the esquema you are
  preparing.

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `369`, `filing_year` and `period` (`aeat app modelo describe 369 --year
   <YEAR> --period <PERIOD>` and `aeat app modelo casillas 369 --year <YEAR>
   --period <PERIOD>`). The casilla set is scoped to the esquema the period
   token selects. See `reference/casillas.md` for the orientation.
2. Tell the person you will create the Modelo 369 work unit for that esquema
   and period in their profile, then create it: operation
   `modelo.work.create` (`aeat app modelo work create --modelo 369 --year
   <YEAR> --period <PERIOD>`). Keep the work unit id it returns.
3. Tell the person you will save a new draft calculation from their ledger,
   then calculate: operation `modelo.work.calculate` (`aeat app modelo work
   calculate <work-unit-id>`). Read any warning notices and pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The values are the snapshot's
   `casilla_values`; each casilla's `legal_refs` and `source_refs` are in its
   `observations` (`aeat app modelo work observations --work-unit-id
   <work-unit-id>`).

## What Modelo 369 adds over the quarterly IVA pattern

- **Few casillas are filled from the ledger.** The registry binds ledger
  invoices to a small set of cuota casillas per esquema (see
  `reference/casillas.md` for which): at present Germany at the general rate
  for all three esquemas, plus France services for Unión. The rest of the form
  (the per-member-state settlement casillas and the control casillas) is
  computed. Do not sum member states yourself, and do not assume an invoice for
  another destination or rate was picked up: check the revision.
- **The esquema total is a partial subtotal.** `iva.union.cuota-total`,
  `iva.exterior.cuota-total` and `iva.importacion.cuota-total` are labelled
  "Subtotal parcial" and "sin correcciones" in the registry. Read the total from
  the calculated revision, never by hand-adding rows, and do not present it to
  the person as the whole OSS/IOSS liability. Say what it covers.
- **No cross-esquema total.** Each esquema's work unit is independently
  calculated and verified; there is no Modelo-369-wide combined casilla across
  Unión, Exterior and Importación.

## Success assertions

- The calculation raised no warning you have not passed on.
- Every per-destination cuota and the esquema total you report is consistent
  with the classified ledger's OSS/IOSS-tagged issued invoices for that member
  state. If an advisory says classified OSS/IOSS invoices were consumed by no
  casilla, tell the person and resolve it in the ledger before going on.
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
