---
name: cadrumo-preparar-modelo-309
description: >-
  Prepare a Modelo 309 (IVA declaración-liquidación no periódica) from the
  classified ledger: create the work unit, calculate the one-off cuota, verify,
  write the local fichero-BOE once the person agrees, and leave the filing to
  the person. Use when the person has a one-off IVA trigger outside their
  periodic schedule, or no periodic IVA obligation at all.
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [RECARGO_EQUIVALENCIA, EXENTO, REAGP, NO_APLICA]
---

# Prepare Modelo 309

Modelo 309 is the ad-hoc IVA declaration for a non-periodic obligation trigger:
an intracommunity acquisition of a new means of transport (or similar
inversión-del-sujeto-pasivo event) under régimen especial de la agricultura, or
a recargo-de-equivalencia retailer's devolución claim on traveler exports.
Cadrumo computes the cuota from the classified ledger; you run the steps and
relay what comes back. Never compute a casilla value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-303` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
differences are the trigger condition (an ad-hoc event, not a
recurring period), the period token (`AD-HOC`, not `1T`-`4T`) and the casilla
shape below.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## When Modelo 309 applies, not Modelo 303

Modelo 309 is for a taxpayer who does NOT have a standing periodic IVA
obligation (no régimen general IVA registration) but incurs a one-off IVA
cuota from a specific trigger event. Confirm the trigger before creating the
work unit; do not default to 309 for a taxpayer who already files periodic
303s, because a periodic filer routes the same economic event through their
next 303 period instead. Ask the person which trigger applies:

- Intracommunity acquisition of a new means of transport (medios de transporte
  nuevos) or a similar inversión-del-sujeto-pasivo event.
- Régimen especial de la agricultura, ganadería y pesca event requiring an
  ad-hoc autorepercusión.
- A recargo-de-equivalencia retailer discharging a devolución to a traveler
  (devolución a viajeros).
- Ejecución forzosa proceedings triggering an ad-hoc IVA obligation.

To see what the registry says about applicability for this profile, read
operation `overview.explain` (`aeat app overview explain 309 --year <YEAR>`):
`applicable`, `verdict`, `rationale` and `profile_facts`.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The ledger transactions for the trigger event are built and classified, with
  IVA categories applied: operation `ledger.check` (`aeat app ledger check`)
  and operation `ledger.ratios.validate` (`aeat app ledger ratios validate`).
  Both only read.
- You know the `filing_year` (the ejercicio the event falls in). The period is
  always the ad-hoc token `AD-HOC`; Modelo 309 has no quarterly or monthly
  variant.

## Procedure

1. Read the form shape. It reads bundled reference data and changes nothing.
   Tool `authority` with `query` `describe`, then `casillas`, giving `modelo`
   `309`, `filing_year` and `period` `AD-HOC` (`aeat app modelo describe 309
   --year <YEAR> --period AD-HOC` and `aeat app modelo casillas 309 --year
   <YEAR> --period AD-HOC`).
2. Tell the person you will create the Modelo 309 work unit for that year in
   their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 309 --year <YEAR> --period AD-HOC`). Keep the
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
   `casilla_values`, its `result_summary` names the headline casilla, and each
   casilla's `legal_refs` and `source_refs` are in its `observations` (`aeat app
   modelo work observations --work-unit-id <work-unit-id>`).

## What the Modelo 309 casilla set holds

Read the casilla list for the exact set; do not rely on this page for numbers.
It has two parts:

- **The form's declaration and liquidation block** (`decl.*`): the declarant
  and trigger data (`decl.tipo-trigger`, `decl.situacion-tributaria`,
  `decl.hecho-imponible`, the vehicle, boat or aircraft fields), the régimen
  general and recargo de equivalencia base/tipo/cuota lines, the computed
  `decl.cuota-devengada-22`, the manual `decl.a-deducir-23` and the computed
  `decl.resultado-24` ("Resultado a ingresar"). Most of these are manual
  casillas: they hold only what the person supplies.
- **Two ledger-bound casillas and their total**:
  - `iva.autorepercutido.intracomunitaria` - cuota IVA autorepercutida on the
    intracommunity acquisition trigger.
  - `iva.soportado.recargo-equivalencia` - cuota IVA soportado on the
    recargo-de-equivalencia devolución trigger.
  - `iva.cuota-no-periodica-total` - computed, the sum of those two.

Which casillas carry a value after calculation, and which one the revision's
`result_summary` names as the result, is for the revision to say. Report that
casilla, not the one you expected.

There is no cross-period carry: a 309 stands alone against its trigger event,
with no binding to a prior 309 or 303. Only one of the two ledger-bound
casillas is typically nonzero for a given trigger; both can be nonzero when two
distinct ad-hoc triggers fall in the same ejercicio.

## Success assertions

- The calculation raised no warning you have not passed on.
- `iva.cuota-no-periodica-total` equals the sum of the two ledger-bound
  casillas. If an advisory says classified IVA lines were consumed by no
  casilla, tell the person and resolve it in the ledger before going on.
- A filing with both ledger-bound casillas at zero is a red flag: confirm the
  trigger event actually produced a classified cuota before proceeding, and do
  not export a zero-cuota 309 on an unclassified or missing ledger entry.
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
