---
name: cadrumo-preparar-modelo-115
description: >-
  Prepare a Modelo 115 (retenciones e ingresos a cuenta sobre rentas o
  rendimientos procedentes del arrendamiento o subarrendamiento de inmuebles
  urbanos) from a classified ledger: create the work unit, calculate the
  quarterly withholding totals, verify, export the fichero-BOE, and hand off
  for the taxpayer to file. Use when the taxpayer withholds retención on rent
  it pays for a local de negocio or other urban premises it leases from a
  landlord.
applies_when:
  profile_facts:
    - fact: pays_rent_with_retencion
      match: is_true
---

# Prepare Modelo 115

Modelo 115 is the quarterly self-assessment of retenciones e ingresos a
cuenta that a retenedor (a business paying rent on an urban premises it
leases - a local de negocio, an office) withholds from the rent it pays and
remits to the AEAT. The CLI computes it from the classified ledger's
withholding schemes; you orchestrate and relay. Never compute a casilla value
yourself.

This skill diffs against `cadrumo-preparar-modelo-111`: the lifecycle spine (work
create -> calculate -> verify -> revision review -> export -> reconcile) and
the ledger-aggregation mechanism are identical in shape. The deltas are: (1)
Modelo 115 has a single ledger-aggregated block, not three or nine, (2)
Modelo 115 is quarterly only - it has no monthly cadence to confirm, and (3)
Modelo 115's annual roll-up is Modelo 180, not Modelo 190.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the quarter records every rent payment the taxpayer made on
  a leased urban premises, with its withholding scheme and rate:
  `aeat app ledger check`. A payment lacking its scheme cannot be aggregated
  into casillas 01-02 below.
- You know the `filing_year` and the `period`. Modelo 115 accepts only the
  quarterly tokens (`1T`-`4T`) - confirm this via
  `aeat app overview explain 115 --year <YEAR>` rather than assuming a
  monthly cadence carries over from Modelo 111.

## Procedure

1. Read the form shape: `aeat app modelo describe 115 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 115 --year <YEAR>
   --period <PERIOD>`. See the `reference/casillas.md` companion for what
   each casilla means.
2. Create the work unit: `aeat app modelo work create --modelo 115 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries
   `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 115 changes from the retenciones pattern

- **One ledger-aggregated block, not several.** Casillas 01 (número de
  perceptores) and 02 (base de retenciones e ingresos a cuenta) are each
  bound to a `retenciones_aggregation` source scoped to the urban-rental
  withholding scheme: casilla 01 is the distinct perceptor (landlord) count,
  casilla 02 is the taxable-base sum. Unlike Modelo 111's nine blocks,
  Modelo 115 has no en-especie or manual-input income block - every
  perceptor and every euro of base the form declares comes from the ledger.
- **Casilla 03** ("Retenciones e ingresos a cuenta") is computed: 19% of
  casilla 02 (`irpf.urban_rental_withholding_rate`, currently 19%, LIRPF art.
  101/RD 439/2007 art. 100 and 108). Reach it through calculate, never by
  re-deriving the percentage.
- **Casilla 04** ("Resultado de anteriores declaraciones") is the one manual
  field: an operator-supplied same-year prior-quarter correction when
  amending. It is not cross-period carried; do not assume it defaults to
  zero without asking whether an amendment applies.
- **Casilla 05** (result to pay) is casilla 03 minus casilla 04.
- **Annual roll-up is Modelo 180, not Modelo 190.** Modelo 180 (the annual
  informativa summarising the year's Modelo 115 filings) folds every
  quarter's casillas 02 and 03 into its own annual base and retenciones
  totals via cross-modelo relations, and independently derives its own
  DISTINCT perceptor-NIF count (not a sum of the quarterly counts, which
  would double-count a landlord paid in more than one quarter). Do not
  prepare Modelo 180 until all four quarters of Modelo 115 for the year are
  calculated and stable - a quarter recalculated afterward invalidates the
  annual figure the same way a stale Modelo 303 quarter invalidates Modelo
  390.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- Casilla 03 (retenciones) is consistent with 19% of casilla 02 (base) as
  reported in the revision; a nonzero perceptor count (01) with a zero base
  or zero retención sum (02/03) is the under-declaration shape to question
  before export (see `cadrumo-operator-grounding`).
- Every reported casilla value is quoted verbatim from the JSON, with its
  `legal_refs`/`source_refs`.

## Verify and hand off

5. Dispatch the verifier as an independent step: `aeat app modelo work verify
   <work-unit-id> --format json`. Treat exit `1` as a verdict; relay every
   finding. Do not export a revision that verifies BLOCKED.
6. When verified clean, export the local artefact: `aeat app modelo export
   <work-unit-id>`. This produces a fichero-BOE file. It is NOT official AEAT
   evidence and the return is NOT filed. Tell the taxpayer to upload it
   themselves in the AEAT portal.
7. After the human files, official evidence is pulled with `aeat app modelo
   reconcile pull` (a justificante), never asserted from the local export.
