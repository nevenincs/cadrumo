---
name: cadrumo-preparar-modelo-202
description: >-
  Prepare a Modelo 202 (pago fraccionado del Impuesto sobre Sociedades) for a
  sociedad: create the work unit, calculate under the modalidad the INCN gate
  selects (art. 40.2 or 40.3 LIS), verify, write the local fichero-BOE once the
  person agrees, and leave the filing to the person. Use when preparing any of the
  three annual instalments (1P/2P/3P) a legal_entity pays on account of its Modelo 200.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [legal_entity]
---

# Prepare Modelo 202

Modelo 202 is the quarterly-cadence (but non-quarterly-period-coded) pago
fraccionado a `legal_entity` taxpayer pays on account of the annual Impuesto
sobre Sociedades (LIS, Ley 27/2014, art. 40): the sociedad counterpart to Modelo
130's IRPF instalment, and the instalment stream that Modelo 200 later folds in
as a credit. Cadrumo computes every casilla; you run the steps and relay what
comes back. Never compute a casilla value yourself.

The lifecycle is the one in `cadrumo-preparar-modelo-130` (work unit, calculate,
verify, revision review, export, reconcile); load that skill to compare. The
form's parent is the annual return in `cadrumo-preparar-modelo-200`, whose
liquidación the year's three instalments feed as a credit (see its "Modelo 202
pagos-fraccionados fold-in" section). The differences are: a registry-enforced
INCN modality gate that selects between two mutually exclusive lanes, a
same-modelo prior-instalment carry within the year, a cross-modelo carry of the
prior year's Modelo 200 cuota as the art. 40.2 instalment base, and a **known,
documented under-declaration gap** on one casilla that you must flag explicitly
rather than let a clean verify imply safety.

Each step names the tool server operation that does the work and, in
parentheses, the `aeat` command it corresponds to. Use the operation; use the
command only if the tool server cannot do the step. `describe` an operation
before you `execute` it. On the command line the output option goes before the
group: `aeat --format json app modelo work calculate <work-unit-id>`.

## Gating precondition

Modelo 202 applies only to a `legal_entity` taxpayer (LIS, Ley 27/2014) obliged
to make pagos fraccionados, never to a natural-person `autonomo` profile, which
files Modelo 130 instead. Confirm applicability from the registry, never from
the entity type alone: operation `overview.explain` (`aeat app overview explain
202 --year <YEAR>`) returns `applicable`, `verdict`, `rationale` and
`profile_facts`. See `cadrumo-pyme-sociedad` for the itinerary that sequences
Modelo 202 alongside Modelo 200 and Modelo 303 for a sociedad.

## Preconditions

- `status` reports a session that admits this server; you work only inside
  that profile.
- The profile declares `entity_type = legal_entity` and its importe neto de la
  cifra de negocios (INCN) for the prior twelve months
  (`incn_prior_12_months`); `profile_facts` in the `overview.explain` result
  shows what is declared. INCN is the sole determinant of which modalidad
  applies. An undeclared INCN blocks calculation rather than guessing: the
  revision's `modality` comes back `incomplete`, never a silently wrong lane. If
  it is missing, ask the person for it; do not assume one.
- For the 2P and 3P instalments of the same `filing_year`, the earlier
  instalment(s) of that year are already calculated: Modelo 202 carries the
  year's own prior instalments as a same-modelo credit (casilla `34` of earlier
  periods, summed into casilla `30`). Read each prior instalment's revision
  before starting a later one: operations `modelo.work.revision` and
  `modelo.work.revision_snapshot` (`aeat app modelo work revision --work-unit-id
  <work-unit-id of that instalment>`).
- For the art. 40.2 modalidad (casilla `03`), the prior year's Modelo 200 is
  calculated or filed in the profile and available: Modelo 202 carries it in as
  the instalment base (casilla `01`). A taxpayer with no prior Modelo 200 gets
  an unresolved casilla `01` with a diagnostic, never a wrong-year bind; confirm
  with the person that this is the expected case rather than assuming it.
- You know the `filing_year` and the instalment `period`: `1P` (April), `2P`
  (October) or `3P` (December). These are NOT the calendar-quarter tokens
  (`1T`-`4T`) the IVA/IRPF quarterly modelos use.

## Procedure

1. Read the form shape before citing any casilla; the registry is the
   authority. It reads bundled reference data and changes nothing. Tool
   `authority` with `query` `describe`, then `casillas`, giving `modelo` `202`,
   `filing_year` and `period` (`aeat app modelo describe 202 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 202 --year <YEAR> --period
   <PERIOD>`). Narrow a read with `casilla_number` or `input_kind` (`--number`
   or `--input-kind` on the command line) instead of paging through the full
   set. See `reference/casillas.md` for the modalidad map.
2. Tell the person you will create the Modelo 202 work unit for that instalment
   in their profile, then create it: operation `modelo.work.create` (`aeat app
   modelo work create --modelo 202 --year <YEAR> --period <PERIOD>`). Keep the
   work unit id it returns.
3. Tell the person you will save a new draft calculation, then calculate:
   operation `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). Most Modelo 202 inputs are manual accounting facts: enter
   one only with a value the person gave you (`--casilla <casilla-id>=<decimal>`
   on the command line; the operation's input schema says where it goes). Read
   any warning notices and pass them on.
4. Read the computed revision: operations `modelo.work.revision` and
   `modelo.work.revision_snapshot` (`aeat app modelo work revision
   --work-unit-id <work-unit-id>`). The values are the snapshot's
   `casilla_values`; the registry-selected lane is its `modality` (with a
   `reason`); each casilla's `legal_refs` and `source_refs` are in its
   `observations` (`aeat app modelo work observations --work-unit-id
   <work-unit-id>`). This is the value set you report to the person.

## What Modelo 202 adds over the Modelo 130 pattern

- **The INCN modality gate selects the applicable lane, not the taxpayer's
  preference.** LIS art. 40.3: when the entity's INCN over the prior twelve
  months exceeds EUR 6.000.000, only the art. 40.3 lane (casilla `32` feeding
  `34`, "Cantidad a ingresar") applies and the art. 40.2 lane (casilla `03`) is
  not offered; at or below that threshold, art. 40.2 is the default and the art.
  40.3 lane may still be elected. The gate is enforced in calculation, driven by
  the `incn_prior_12_months` fact, and reported as the revision's `modality`:
  `art_40_2_optional`, `art_40_3_mandatory` or `incomplete`. Never assume the
  modalidad from the entity's size or form; read which lane the calculated
  revision actually populated.
- **The art. 40.3 lane has two mutually exclusive sub-lanes of its own, B1 and
  B2.** Casilla `18` (B1, caso general: a single tipo de gravamen) and casilla
  `26` (B2, casos específicos: multiple tipos de gravamen across tramos) are
  alternative computations of the same "resultado previo" the AEAT instructions
  describe as "clave [18] (o clave [26])". A filer completes exactly one lane's
  manual inputs and leaves the other's blank so it resolves to zero. Casilla
  `32` takes `18 + 26`, reproducing the "o" selection without a lane flag. Read
  whichever lane the person's manual inputs populated from the calculated `32`;
  never assume which sub-lane applies from the entity's structure alone.
- **Same-modelo cross-period carry within the year.** Casilla `34` from every
  earlier instalment of the same `filing_year` is summed into casilla `30` as a
  credit (binding `modelo-202-pagos-fraccionados-anteriores`, never a total you
  compute by hand). For `2P` and `3P`, confirm the earlier instalment(s) were
  calculated before trusting this credit; a missing prior instalment silently
  narrows the credit rather than blocking the current one.
- **Cross-modelo carry of the prior Modelo 200 as the art. 40.2 base.** Casilla
  `01` (base del pago fraccionado, art. 40.2) is bound to the prior Modelo 200's
  cuota del ejercicio a ingresar o a devolver (`DP200014B:00599`), which is the
  cuota líquida net of retenciones e ingresos a cuenta, as the art. 40.2
  instructions require. The registry declares the binding for `1P`, `2P` and
  `3P`: `2P` and `3P` read one filing year back (the prior year's July deadline
  has elapsed by then), `1P` reads two years back (LIS art. 40.2, "último
  período... cuyo plazo... estuviese vencido"). It resolves only from a Modelo
  200 for that year in the profile; otherwise casilla `01` stays unresolved with
  a diagnostic. Never assert this value yourself: read it from the calculated
  revision and confirm with the person when a prior filing cannot be resolved.
  For a taxpayer whose INCN exceeds EUR 6.000.000, casilla `01` is not
  populated, because only art. 40.3 applies.
- **Known, documented under-declaration gap: casilla `33` has no safe guard.**
  Casilla `33` ("Mínimo a ingresar, CN >= 10 millones euros") is a manual input
  with no formula or binding linkage in any revision, and casilla `34` is the
  larger of `32` and `33`. The large-taxpayer minimum-payment-on-account floor
  it represents (INCN >= EUR 10.000.000, filing periods from 2024) is NOT
  grounded in the bundled legal catalogue or corpus, and no antecedent casilla
  exists that would make an `implies_nonzero` guard false-positive-free (casilla
  `04`, the nearest candidate, is legitimately positive for the overwhelming
  majority of filers who are correctly below the INCN threshold and correctly
  leave `33` blank). **This is a documented non-guard, not a resolved gap: if
  the person's INCN is at or above EUR 10.000.000, ask them explicitly whether
  the minimum-payment floor applies. Cadrumo will not surface any advisory or
  block on a silently blank casilla `33` for such a filer.** If they give you a
  figure, it is theirs to supply; pass it as a manual casilla and attribute it
  to them.
- **The B2 sub-lane's per-tramo bases (2025-only) are advisory-guarded.**
  Casillas `61`/`64` (base a tipo 3 / tipo 4) each feed a formula-derived
  importe (`63`/`66`, `importe = base x porcentaje`, with `62`/`65` the
  porcentaje); a positive declared base with a zero computed importe is a
  non-blocking advisory worth confirming, not a silent pass-through.

## Success assertions

Before handing off, confirm in the revision:

- The calculation raised no warning you have not passed on.
- **Modalidad correctly selected.** The populated lane (casilla `03` for art.
  40.2, or casilla `32`/`34` for art. 40.3) matches the revision's `modality`
  and what the INCN gate implies. If the person expected the other lane, treat
  it as suspect and confirm the declared `incn_prior_12_months` before
  proceeding.
- **Base imponible previa determinada cuando el resultado es positivo.** When
  casilla `04` (resultado contable después del IS, manual) is strictly
  positive, casilla `13` (base imponible previa, formula-derived from `04` plus
  correcciones) must not silently resolve to zero with no declared corrección
  explaining it. A non-blocking advisory surfaces this; confirm with the person
  rather than assume either way.
- **B1/B2 mutual exclusivity.** At most one of casilla `18` (B1) and casilla
  `26` (B2) is positive. Verification blocks a filing where both alternative
  lanes were populated, since that would overstate the resultado previo.
- **B2 tramo base-to-importe consistency (2025-only).** A positive `61` or `64`
  implies a nonzero `63`/`66` respectively; the guards are non-blocking
  advisories.
- **Casilla `33` (minimum-payment floor) explicitly confirmed for large
  taxpayers.** If the person's INCN is at or above EUR 10.000.000, do not treat
  a blank casilla `33` as sufficient: ask directly whether the floor applies,
  since no guard covers this casilla (see above).
- Every reported casilla value is quoted verbatim from the revision, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Verify: operation `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft and records a
   verification report. Read `completeness_status` (`complete`, `incomplete` or
   `blocked`), every entry of `findings` (advisories included, especially the
   casilla `13` and B2-tramo advisories above) and `missing_required_casilla_ids`.
   Relay every finding. The command exits `1` for `incomplete` and `blocked`;
   that is a verdict, not a crash. Do not export a `blocked` revision (the
   B1/B2 mutual-exclusivity check blocks a dual-populated filing).
6. When verified clean, say what you are about to do and wait for the person's
   go-ahead in the conversation: you will write a local fichero-BOE for the
   verified revision to a path in the conversation workspace; nothing goes to
   AEAT. Then export: operation `modelo.export` (`aeat app modelo export
   <work-unit-id> --output <path>`). The file is not official AEAT evidence and
   the return is not filed; the person uploads it themselves in the AEAT portal
   (Sociedades WEB).
7. After the person says they have filed, tell them you will read the evidence
   AEAT holds (read only on the AEAT side) and compare it with the saved
   calculation, then run operation `modelo.reconcile.pull` (`aeat app modelo
   reconcile pull <work-unit-id>`). Relay the verdict and every difference
   verbatim; official evidence comes from that pull, never from the local
   export.
8. Once all obligatory instalments (1P/2P/3P) for the `filing_year` are filed,
   load `cadrumo-preparar-modelo-200` for the annual return: it folds this
   year's instalments in as a credit against the cuota diferencial.
