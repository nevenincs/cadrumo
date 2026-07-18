---
name: cadrumo-preparar-modelo-202
description: >-
  Prepare a Modelo 202 (pago fraccionado del Impuesto sobre Sociedades) for a
  legal_entity taxpayer: create the work unit, calculate the applicable
  modalidad (art. 40.2 or art. 40.3 LIS), verify, export the fichero-BOE, and
  hand off for the taxpayer to file. Use for each of the three annual
  instalments (1P/2P/3P) a sociedad is obliged to pay on account of the year's
  Modelo 200.
applies_when:
  profile_facts:
    - fact: entity_type
      match: equals
      values: [legal_entity]
---

# Prepare Modelo 202

Modelo 202 is the quarterly-cadence (but non-quarterly-period-coded) pago
fraccionado a `legal_entity` taxpayer pays on account of the annual Impuesto
sobre Sociedades (LIS, Ley 27/2014, art. 40) - the sociedad counterpart to
Modelo 130's IRPF instalment, and the instalment stream that Modelo 200 later
folds in as a credit. The CLI computes every casilla; you orchestrate and
relay. Never compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-130` (the shared pago-fraccionado
spine: work create -> calculate -> verify -> revision review -> export ->
reconcile is identical) and `cadrumo-preparar-modelo-200` (M202's own parent form,
whose annual liquidación the year's three instalments feed as a credit - see
its "Modelo 202 pagos-fraccionados fold-in" section). The delta is: a
registry-enforced INCN modality gate that selects between two mutually
exclusive lanes, a same-modelo prior-instalment carry within the year, a
cross-modelo carry of the prior year's Modelo 200 cuota as the art. 40.2
instalment base, and a **known, documented under-declaration gap** on one
casilla this skill must flag explicitly rather than let a clean verify imply
safety.

## Gating precondition

Modelo 202 applies only to a `legal_entity` taxpayer (LIS, Ley 27/2014) obliged
to make pagos fraccionados - never to a natural-person `autonomo` profile,
which files Modelo 130 instead. Confirm applicability from the CLI, never from
the entity type alone: `aeat app overview explain 202 --year <YEAR>`. See
`cadrumo-pyme-sociedad` for the itinerary that sequences Modelo 202 alongside Modelo
200 and Modelo 303 for a sociedad.

## Preconditions

- An active profile exists and declares `entity_type = legal_entity` and its
  importe neto de la cifra de negocios (INCN) for the prior twelve months
  (`incn_prior_12_months`) - `aeat app overview status`. INCN is the sole
  determinant of which modalidad applies; an undeclared INCN blocks
  calculation rather than guessing (the engine returns INCOMPLETE, never a
  silently-wrong modality).
- For the 2P and 3P instalments of the same `filing_year`, the earlier
  instalment(s) of that year are already calculated - Modelo 202 carries the
  year's own prior instalments as a same-modelo credit (casilla `34` from
  earlier periods, summed). Read each prior instalment's revision with
  `aeat app modelo work revision <work-unit-id> --format json` before starting
  a later one.
- For the art. 40.2 modalidad (casilla `03`), the prior year's Modelo 200 cuota
  líquida is filed and available - Modelo 202 carries it in as the instalment
  base (casilla `01`). A first-year filer with no prior Modelo 200 gets a
  zero-carry, never a wrong-year bind; confirm this is the expected case rather
  than assuming.
- The `filing_year` and the instalment `period` - `1P` (April), `2P` (October),
  or `3P` (December). These are NOT the calendar-quarter tokens (`1T`-`4T`)
  the IVA/IRPF quarterly modelos use.

## Procedure

1. Read the form shape before citing any casilla - the registry is the
   authority: `aeat app modelo describe 202 --year <YEAR> --period <PERIOD>`
   and `aeat app modelo casillas 202 --year <YEAR> --period <PERIOD>`. Narrow a
   read with `--number` or `--input-kind` instead of paging through the full
   set. See `reference/casillas.md` for the modalidad map.
2. Create the work unit: `aeat app modelo work create --modelo 202 --year
   <YEAR> --period <PERIOD>`. Read the envelope; note the work-unit id it
   returns.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`. Every casilla carries `legal_refs` and
   `source_refs` - keep them.
4. Read the computed revision:
   `aeat app modelo work revision <work-unit-id> --format json`. This is the
   value set you report to the taxpayer.

## What Modelo 202 adds over the Modelo 130 pattern

- **The INCN modality gate selects the applicable lane, not the taxpayer's
  preference.** LIS art. 40.3: when the entity's INCN over the prior twelve
  months exceeds EUR 6.000.000, only the art. 40.3 lane (casilla `32` feeding
  `34`, "Cantidad a ingresar") applies and the art. 40.2 lane (casilla `03`) is
  not offered; at or below that threshold, art. 40.2 is the default and art.
  40.3 lane may still be elected. The gate is enforced in calculation
  (`derive_modelo_202_modality`), driven by the `incn_prior_12_months`
  binding - never assume the modalidad from the entity's size or form; read
  which lane the calculated revision actually populated.
- **The art. 40.3 lane has two mutually exclusive sub-lanes of its own,
  B1 and B2.** Casilla `18` (B1, caso general - a single tipo de gravamen) and
  casilla `26` (B2, casos específicos - multiple tipos de gravamen across
  tramos) are alternative computations of the same "resultado previo" the AEAT
  instructions describe as "clave [18] (o clave [26])"; a filer completes
  exactly one lane's manual inputs and leaves the other's blank so it
  resolves to zero. Casilla `32` sums both (`18 + 26`), reproducing the "o"
  selection without a registry lane-discriminator flag. Read whichever lane
  the taxpayer's manual inputs populated from the calculated `32`, never
  assume which sub-lane applies from the entity's structure alone.
- **Same-modelo cross-period carry within the year.** Casilla `34` from every
  earlier instalment of the same `filing_year` is summed and applied as a
  credit (`modelo-202-...-pagos-fraccionados-anteriores`, a `relation_prefill`
  binding, never a total you compute by hand). For `2P` and `3P`, confirm the
  earlier instalment(s) were calculated before trusting this credit; a missing
  prior instalment silently narrows the credit rather than blocking the
  current one.
- **Cross-modelo carry of the prior Modelo 200 cuota as the art. 40.2 base.**
  Casilla `01` (base del pago fraccionado, art. 40.2) is a `relation_prefill`
  binding copying the prior Modelo 200's cuota líquida
  (`DP200014B:00592`) - 2P/3P bind one year back (after the prior year's July
  deadline has elapsed), 1P legally binds two years back per LIS art. 40.2
  ("último período... cuyo plazo... estuviese vencido") but the registry
  currently resolves this relation only for 2P/3P; for 1P the base is
  operator-entered until Modelo 200 source coverage extends earlier. Never
  assert this value yourself - read it from the calculated revision and
  confirm with the taxpayer when a prior filing cannot be resolved.
- **Known, documented under-declaration gap: casilla `33` has no safe
  guard.** Casilla `33` ("Mínimo a ingresar, CN >= 10 millones euros") is a
  manual input with no formula or binding linkage in any revision. The
  large-taxpayer minimum-payment-on-account floor it represents (INCN >= EUR
  10.000.000, filing periods from 2024) is NOT grounded in this codebase's
  legal catalogue or bundled corpus, and no antecedent casilla exists that
  would make an `implies_nonzero` guard false-positive-free (casilla `04`,
  the nearest candidate, is legitimately positive for the overwhelming
  majority of filers who are correctly below the INCN threshold and correctly
  leave `33` blank). **This is a documented non-guard, not a resolved gap: if
  the taxpayer's INCN is at or above EUR 10.000.000, you must ask explicitly
  whether the minimum-payment floor applies and route the answer to the role
  that owns operator-entered facts - the CLI will not surface any advisory or
  block on a silently-blank casilla `33` for such a filer.**
- **The B2 sub-lane's per-tramo bases (2025-only) are ADVISORY-guarded.**
  Casillas `61`/`64` (base a tipo 3 / tipo 4) each feed a formula-derived
  importe (`63`/`66` respectively, `importe = base x porcentaje`); a positive
  declared base with a zero computed importe is a non-blocking advisory
  worth confirming, not a silent pass-through.

## Success assertions

Before handing off, confirm in the calculate / revision JSON:

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- **Modalidad correctly dispatched.** The populated lane (casilla `03` for
  art. 40.2, or casilla `32`/`34` for art. 40.3) matches what the INCN gate
  implies; if the taxpayer expected the other lane, treat it as suspect and
  confirm the declared `incn_prior_12_months` before proceeding.
- **Base imponible previa determinada cuando el resultado es positivo.** When
  casilla `04` (resultado contable después del IS, manual) is strictly
  positive, casilla `13` (base imponible previa, formula-derived from `04` +
  correcciones) must not silently resolve to zero with no declared corrección
  explaining it - a non-blocking advisory surfaces this; confirm with the
  taxpayer rather than assume either way.
- **B1/B2 mutual exclusivity.** At most one of casilla `18` (B1) and casilla
  `26` (B2) is positive - the registry BLOCKS a filing where both alternative
  lanes were populated, since that would overstate the resultado previo.
- **B2 tramo base-to-importe consistency (2025-only).** A positive `61` or
  `64` implies a nonzero `63`/`66` respectively - non-blocking advisories.
- **Casilla `33` (minimum-payment floor) explicitly confirmed for large
  taxpayers.** If the taxpayer's INCN is at or above EUR 10.000.000, do not
  treat a blank casilla `33` as sufficient - ask the taxpayer directly whether
  the minimum-payment-on-account floor applies, since no CLI guard covers this
  casilla (see above).
- Every reported casilla value is quoted verbatim from the JSON, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Dispatch the verifier as an independent step:
   `aeat app modelo work verify <work-unit-id> --format json`. Treat exit `1`
   as a verdict; relay every finding, including advisories - especially the
   casilla `13` and B2-tramo advisories above. Do not export a revision that
   verifies BLOCKED (the B1/B2 mutual-exclusivity check will BLOCK a
   dual-populated filing).
6. When verified clean, export the local artefact:
   `aeat app modelo export <work-unit-id>`. This produces a fichero-BOE file.
   It is NOT official AEAT evidence and the return is NOT filed. Tell the
   taxpayer to upload it themselves in the AEAT portal (Sociedades WEB).
7. After the human files, official evidence is pulled with
   `aeat app modelo reconcile pull` (a justificante), never asserted from the
   local export.
8. Once all obligatory instalments (1P/2P/3P) for the `filing_year` are filed,
   hand off to `cadrumo-preparar-modelo-200` for the annual return - it folds this
   year's instalments in as a credit against the cuota diferencial.
