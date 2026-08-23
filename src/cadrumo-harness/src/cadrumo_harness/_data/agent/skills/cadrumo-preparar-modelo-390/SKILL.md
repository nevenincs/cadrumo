---
name: cadrumo-preparar-modelo-390
description: >-
  Prepare a Modelo 390 (IVA declaración-resumen anual) from the four already-filed
  quarterly Modelo 303s: create the work unit, calculate the annual IVA summary,
  verify it reconciles against the four trimestrales, export the fichero-BOE, and
  hand off for the taxpayer to file. Use when the taxpayer files their annual IVA
  summary declaration.
applies_when:
  profile_facts:
    - fact: iva_regime
      match: equals
      values: [GENERAL, SIMPLIFICADO]
---

# Prepare Modelo 390

Modelo 390 is the annual IVA declaración-resumen: it does not compute a new IVA
result, it reconciles the year's ledger-derived annual totals against the sum of
the four quarterly Modelo 303 autoliquidaciones already filed for the same
`filing_year`. The CLI computes and reconciles it; you orchestrate and relay.
Never compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the precondition (all four 303 quarters, not one) and the
verify step (an inter-modelo reconciliation gate, not just a completeness check).

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the full `filing_year` is built and classified: IVA categories
  and prorrata are applied across all four quarters
  (`aeat app ledger check`, `aeat app ledger ratios validate`).
- **All four Modelo 303 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated** — read each with
  `aeat app modelo work revision <work-unit-id> --format json` before starting
  the 390. Modelo 390 folds these four filings into its annual totals; a missing
  or stale quarter blocks verification (see below).
- The `filing_year`. The period is always the annual token `0A` — Modelo 390 has
  no quarterly variant.

## Procedure

1. Read the form shape: `aeat app modelo describe 390 --year <YEAR>
   --period 0A` and `aeat app modelo casillas 390 --year <YEAR> --period 0A`.
2. Create the work unit: `aeat app modelo work create --modelo 390 --year <YEAR>
   --period 0A`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`. Read
   `result` and `notices`; every casilla carries `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 390 adds over the quarterly pattern

- **Annual totals** are ledger-derived directly (`iva.anual.cuota-devengada-total`,
  `iva.anual.cuota-deducible-total`, `iva.anual.resultado-regimen-general`) —
  the same repercutido/soportado/recargo/intracomunitaria shape as Modelo 303,
  summed over the whole year instead of one quarter.
- **Reconciliation casillas** (`iva.anual.reconciliacion.devengada-303`,
  `iva.anual.reconciliacion.deducible-303`,
  `iva.anual.reconciliacion.resultado-303`) pull the same three totals from the
  four Modelo 303 quarters via cross-modelo relations, independently of the
  ledger.
- **Casilla 79** (régimen simplificado, "IVA devengado — Total cuota
  resultante") carries the 4T Modelo 303's casilla 54 verbatim — régimen
  simplificado settles once a year in the 4T filing, not summed across quarters.
- **Casillas 97 and 662** (compensación pendiente) partition the year's IVA
  wallet compensación state across the four 303 quarters: casilla 97 is the
  amount to compensate carried from the last period of the year, casilla 662 is
  compensación generated during the year outside that last-period amount.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The annual ledger-derived totals are consistent with the four quarters'
  declared IVA devengado/deducible; act on any unconsumed-declarable-IVA
  advisory the CLI surfaces.
- Every reported value is quoted verbatim from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id> --format
   json`. Modelo 390 verification is a **blocking equality gate**: the
   ledger-derived annual cuota devengada, cuota deducible, and resultado each
   must equal the corresponding total reconciled from the four 303 quarters. A
   `BLOCKING_RULE` finding here means a quarter is missing, stale, or was
   recalculated after 390 was created — re-check each 303 quarter's revision
   before retrying, never edit the 390 casilla to force a match. Treat exit `1`
   as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is NOT
   official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
