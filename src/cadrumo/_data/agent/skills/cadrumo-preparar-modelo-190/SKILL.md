---
name: cadrumo-preparar-modelo-190
description: >-
  Prepare a Modelo 190 (resumen anual de retenciones e ingresos a cuenta del
  trabajo y de actividades económicas) from the four already-calculated
  quarterly Modelo 111s: create the work unit, calculate the annual summary,
  verify it reconciles against the four trimestrales, review the per-perceptor
  detail rows, export the fichero-BOE, and hand off for the taxpayer to file.
  Use when the taxpayer files their annual retenciones informativa summary.
applies_when:
  profile_match: any
  profile_facts:
    - fact: has_employees
      match: is_true
    - fact: pays_professionals_with_retencion
      match: is_true
---

# Prepare Modelo 190

Modelo 190 is the annual retenciones e ingresos a cuenta declaración
informativa: it does not compute a new withholding result, it folds the
year's four quarterly Modelo 111 self-assessments into annual totals and adds
a per-perceptor breakdown (who was paid what, and how much was withheld from
them). The CLI computes and folds it; you orchestrate and relay. Never
compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-390`: Modelo 190 is to Modelo 111
what Modelo 390 is to Modelo 303 — an annual informativa that reconciles
against four already-filed quarterly self-assessments of the same tax
category. The lifecycle spine (work create → calculate → verify → revision
review → export → reconcile) is identical. The delta is the source modelo
(111, not 303), the fold-in mechanism (a direct `annual_summary` relation
sum, not a separate reconciliation-casilla block), and the addition of
per-perceptor detail rows that Modelo 390 has no equivalent of.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the full `filing_year` is built and classified: every
  withheld payment carries its withholding scheme, rate, and perceptor
  identity across all four quarters (`aeat app ledger check`).
- **All four Modelo 111 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated** — read each with
  `aeat app modelo work revision <work-unit-id> --format json` before
  starting the 190. Modelo 190 folds these four filings' casillas
  02/05/08/11/14/17/20/23/26/28 into its annual totals; a missing or stale
  quarter blocks verification (see below). Confirm the taxpayer actually
  files Modelo 111 on quarterly cadence via
  `aeat app overview explain 111 --year <YEAR>` before assuming it — the
  registry folds only the `1T`-`4T` quarterly tokens into Modelo 190; a
  monthly-cadence Modelo 111 filer is out of scope for this skill's
  automatic fold-in and needs the operator's explicit attention.
- The `filing_year`. The period is always the annual token `0A` — Modelo 190
  has no quarterly variant.

## Procedure

1. Read the form shape: `aeat app modelo describe 190 --year <YEAR>
   --period 0A` and `aeat app modelo casillas 190 --year <YEAR> --period
   0A`. See the `reference/casillas.md` companion for what each casilla and
   the per-perceptor rows mean.
2. Create the work unit: `aeat app modelo work create --modelo 190 --year
   <YEAR> --period 0A`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla and every per-perceptor row
   carries `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 190 adds over the annual-informativa pattern

- **Three declarante-level summary casillas**, each folding all four
  Modelo 111 quarters via `annual_summary` relations, never re-summed by
  hand:
  - **Casilla "Número total de percepciones"** — the count of distinct
    perceptor/clave/subclave records for the year, computed directly from
    the per-perceptor withholding store (a `count_distinct` fact), not a
    sum of the four quarters' perceptor counts (a perceptor paid in more
    than one quarter is not double-counted).
  - **Casilla "Importe total de las percepciones"** — the sum of every
    Modelo 111 income block's annual total (trabajo dinerario/especie,
    actividades económicas dinerario/especie, premios dinerario/especie,
    ganancias patrimoniales dinerario/especie, derechos de imagen), each
    itself the year's four quarters of the corresponding Modelo 111 casilla
    (02, 05, 08, 11, 14, 17, 20, 23, 26) summed.
  - **Casilla "Importe total de retenciones e ingresos a cuenta"** — the
    year's four Modelo 111 casilla-28 totals (each quarter's own total
    retenciones) summed.
- **Per-perceptor detail rows.** Unlike Modelo 390 (which has no row-level
  detail), Modelo 190 is an informativa: it reports one row per distinct
  (perceptor, clave, subclave) combination for the year — tax id, legal
  name, clave/subclave (the income-and-withholding-scheme code), the
  dinerario and especie amounts perceived, the retención practicada, and
  the ingreso a cuenta. These rows are ledger-derived from the same
  withholding store the declarante-level totals draw from; do not
  hand-construct or edit a perceptor row.
- **No trabajo-en-especie / manual-block distinction at this layer.**
  Modelo 111's manual (non-ledger-derived) blocks — trabajo en especie,
  ganancias patrimoniales forestales, cesión de derechos de imagen — still
  fold into Modelo 190's totals through the same relations as the
  ledger-derived blocks, once they are entered and calculated on each
  Modelo 111 quarter. A manual block left at `0` on a quarter folds forward
  as `0` into the annual total; question a suspicious `0` on the source
  Modelo 111 quarter (see `cadrumo-preparar-modelo-111`), not on the 190.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The annual totals are consistent with the four quarters' declared
  Modelo 111 casillas; a nonzero perceptor count with a zero total
  percepciones or zero total retenciones is the under-declaration shape to
  question before export.
- Every reported casilla and per-perceptor row value is quoted verbatim
  from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id>
   --format json`. Modelo 190 verification is a **blocking equality gate**:
   the annual perceptions count, perceptions amount, and retenciones amount
   each must equal the corresponding total folded from the four Modelo 111
   quarters. A `BLOCKING_RULE` finding here means a quarter is missing,
   stale, or was recalculated after 190 was created — re-check each 111
   quarter's revision before retrying, never edit the 190 casilla to force
   a match. Treat exit `1` as a verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
