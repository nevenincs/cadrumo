---
name: cadrumo-preparar-modelo-303
description: >-
  Prepare a Modelo 303 (IVA autoliquidación) from a classified ledger: create the
  work unit, calculate the IVA result, verify, export the fichero-BOE, and hand off
  for the taxpayer to file. Use when the taxpayer files their periodic VAT return.
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [GENERAL, SIMPLIFICADO]
---

# Prepare Modelo 303

Modelo 303 is the periodic IVA self-assessment. The CLI computes the IVA result
from the classified ledger; you orchestrate and relay. Never compute a casilla
value yourself.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the period is built and classified: IVA categories and prorrata
  are applied (`aeat app ledger check`, `aeat app ledger ratios validate`).
- You know the `filing_year` and the `period` (`1T`-`4T`, or a monthly token).

## Procedure

1. Read the form shape: `aeat app modelo describe 303 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 303 --year <YEAR>
   --period <PERIOD>`.
2. Create the work unit: `aeat app modelo work create --modelo 303 --year <YEAR>
   --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`. Read
   `result` and `notices`; every casilla carries `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## Compensación pendiente (the IVA wallet carry-forward)

When a quarter's IVA deducible exceeds IVA devengado, the excess does not
vanish: LIVA arts. 99 and 115-116 let it carry forward and offset a future
quarter's cuota instead of being refunded immediately. The registry models
this as four casillas per quarter, chained across periods:

- **Casilla 110** (`iva.compensacion-pendiente-periodos-anteriores`) - the
  balance carried IN from the prior quarter's casilla 87, resolved as a
  `previous_filing` binding (`modelo-303-compensacion-pendiente-anteriores`).
  Never enter this by hand; it is bound.
- **Casilla 78** (`iva.compensacion-aplicada-periodo`) - the portion of
  casilla 110 actually applied against this quarter's resultado, computed by
  the registry formula.
- **Casilla 87** (`iva.compensacion-pendiente-periodos-posteriores`) - the
  remaining balance carried OUT to the next quarter's casilla 110.
- **Casilla 69** (`iva.resultado`) - the quarter's resultado
  (`[66]+[77]+[68]-[78]`), so a nonzero casilla 78 reduces what would
  otherwise be payable.

Read `aeat app modelo work revision <work-unit-id> --format json` and confirm
casilla 110 matches the prior quarter's casilla 87 before treating a quarter
as ready to verify; a mismatch means the prior quarter was recalculated after
this one was created, and this quarter must be recreated against the current
chain. The first quarter of a filing_year (or a taxpayer's first-ever 303)
carries casilla 110 = 0. Never override casilla 110 or 87 to force a balance;
the chain is registry-computed end to end.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The IVA result casilla is consistent with the declared IVA devengado less IVA
  deducible; act on any unconsumed-declarable-IVA advisory the CLI surfaces.
- If casilla 87 (or 110) is nonzero, the next quarter's work unit must reflect
  it before that quarter is verified.
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is NOT
   official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
