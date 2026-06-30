---
name: preparar-modelo-303
description: >-
  Prepare a Modelo 303 (IVA autoliquidación) from a classified ledger: create the
  work unit, calculate the IVA result, verify, export the fichero-BOE, and hand off
  for the taxpayer to file. Use when the taxpayer files their periodic VAT return.
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

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The IVA result casilla is consistent with the declared IVA devengado less IVA
  deducible; act on any unconsumed-declarable-IVA advisory the CLI surfaces.
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is NOT
   official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
