---
name: cadrumo-preparar-modelo-193
description: >-
  Prepare a Modelo 193 (resumen anual de retenciones e ingresos a cuenta sobre
  determinados rendimientos del capital mobiliario) from the four
  already-calculated quarterly Modelo 123s: create the work unit, calculate
  the annual summary, verify it reconciles against the four trimestrales,
  review the per-perceptor detail rows, export the fichero-BOE, and hand off
  for the taxpayer to file. Use when the taxpayer withholds retención on
  rendimientos del capital mobiliario (interest, dividends, and certain other
  capital-income payments) and must summarise the year's Modelo 123 filings.
applies_when:
  profile_facts:
    - fact: pays_capital_income_with_retencion
      match: is_true
---

# Prepare Modelo 193

Modelo 193 is the annual retenciones e ingresos a cuenta declaración
informativa for rendimientos del capital mobiliario: it does not compute a new
withholding result, it folds the year's four quarterly Modelo 123
self-assessments into annual totals and adds a per-perceptor breakdown (who
was paid what capital income, and how much was withheld from them). The CLI
computes and folds it; you orchestrate and relay. Never compute a casilla
value yourself.

This skill diffs against `cadrumo-preparar-modelo-190`: Modelo 193 is to Modelo 123
what Modelo 190 is to Modelo 111 — an annual informativa that reconciles
against four already-filed quarterly self-assessments of the same
retenciones tax category, with a per-perceptor detail block. The lifecycle
spine (work create → calculate → verify → revision review → export →
reconcile) is identical. The delta is the source modelo (123, capital
mobiliario, not 111, trabajo/actividades), the fold-in shape (two summed
totals plus a distinct-perceptor count, not nine income blocks), and the
per-perceptor row content (a single clave per perceptor, not a
clave/subclave combination across nine income categories).

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the full `filing_year` is built and classified: every
  capital-income payment subject to retención carries its withholding
  scheme, rate, and perceptor identity across all four quarters
  (`aeat app ledger check`).
- **All four Modelo 123 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated** — read each with
  `aeat app modelo work revision <work-unit-id> --format json` before
  starting the 193. Modelo 193 folds these four filings' casilla `06` (base
  total) and casilla `09` (retenciones total) into its own annual totals via
  the `annual_summary` relation; a missing or stale quarter blocks
  verification (see below). Confirm the taxpayer actually files Modelo 123
  on quarterly cadence via `aeat app overview explain 123 --year <YEAR>`
  before assuming it.
- The `filing_year`. The period is always the annual token `0A` — Modelo 193
  has no quarterly variant.

## Procedure

1. Read the form shape: `aeat app modelo describe 193 --year <YEAR>
   --period 0A` and `aeat app modelo casillas 193 --year <YEAR> --period
   0A`. See the `reference/casillas.md` companion for what each casilla and
   the per-perceptor rows mean.
2. Create the work unit: `aeat app modelo work create --modelo 193 --year
   <YEAR> --period 0A`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla and every per-perceptor row
   carries `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 193 adds over the annual-informativa pattern

- **Three declarante-level summary casillas**, each folding all four
  Modelo 123 quarters, never re-summed by hand:
  - **Casilla "Numero total de perceptores"** — the count of distinct
    perceptors for the year, computed directly from the dedicated
    per-perceptor retención store (a `perceptor_count_distinct` fact), not a
    sum of the four quarters' perceptor counts (a perceptor paid in more
    than one quarter is not double-counted).
  - **Casilla "Base retenciones e ingresos a cuenta total"** — the year's
    four Modelo 123 casilla-`06` totals (each quarter's own base total)
    summed via an `annual_summary` relation.
  - **Casilla "Retenciones e ingresos a cuenta total"** — the year's four
    Modelo 123 casilla-`09` totals (each quarter's own retenciones total)
    summed via an `annual_summary` relation.
- **Per-perceptor detail rows.** Unlike Modelo 390 (which has no row-level
  detail), Modelo 193 is an informativa: it reports one row per distinct
  perceptor for the year — tax id, legal name, clave (the capital-income
  category code, e.g. intereses de cuentas, dividendos), the amount
  perceived (dinerario), and the retención practicada. These rows are
  ledger-derived from the same withholding store the declarante-level
  totals draw from; do not hand-construct or edit a perceptor row.
- **No manual-block distinction at this layer.** Every declarante total and
  every perceptor row on Modelo 193 is ledger-derived through the
  `retenciones_aggregation` and `withholding` binding sources; there is no
  manual (non-ledger-derived) income block equivalent to Modelo 111's
  trabajo-en-especie or ganancias-forestales casillas. A suspicious `0` on
  any Modelo 193 total traces back to a Modelo 123 quarter that is missing,
  stale, or has an unclassified ledger entry — check the source quarter, not
  the 193.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The annual totals are consistent with the four quarters' declared
  Modelo 123 casillas `06` and `09`; a nonzero perceptor count with a zero
  total base or zero total retenciones is the under-declaration shape to
  question before export.
- Every reported casilla and per-perceptor row value is quoted verbatim
  from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id>
   --format json`. Modelo 193 verification is a **blocking equality gate**:
   the annual base total and retenciones total each must equal the
   corresponding total folded from the four Modelo 123 quarters. A
   `BLOCKING_RULE` finding here means a quarter is missing, stale, or was
   recalculated after 193 was created — re-check each 123 quarter's
   revision before retrying, never edit the 193 casilla to force a match.
   Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
