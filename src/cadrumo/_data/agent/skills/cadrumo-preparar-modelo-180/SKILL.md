---
name: cadrumo-preparar-modelo-180
description: >-
  Prepare a Modelo 180 (resumen anual de retenciones e ingresos a cuenta sobre
  rentas procedentes del arrendamiento de inmuebles urbanos) from the four
  already-calculated quarterly Modelo 115s: create the work unit, calculate
  the annual summary, verify it reconciles against the four trimestrales,
  review the per-perceptor (landlord) detail rows, export the fichero-BOE,
  and hand off for the taxpayer to file. Use when the taxpayer files their
  annual urban-rental retenciones informativa summary.
applies_when:
  profile_facts:
    - fact: pays_rent_with_retencion
      match: is_true
---

# Prepare Modelo 180

Modelo 180 is the annual retenciones e ingresos a cuenta declaración
informativa for urban-premises rental: it does not compute a new withholding
result, it folds the year's four quarterly Modelo 115 self-assessments into
annual totals and adds a per-perceptor breakdown (which landlord was paid
what, and how much was withheld from them). The CLI computes and folds it;
you orchestrate and relay. Never compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-190`: Modelo 180 is to Modelo 115
what Modelo 190 is to Modelo 111 — an annual informativa that reconciles
against four already-filed quarterly self-assessments of the same
withholding concept. The lifecycle spine (work create → calculate → verify →
revision review → export → reconcile) is identical. The delta is the source
modelo (115, not 111), the narrower fold-in (a single ledger-aggregated
block, not up to nine income blocks), and — the load-bearing difference —
Modelo 180's per-perceptor detail rows are **manual input**, not
ledger-derived like Modelo 190's.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- **All four Modelo 115 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated** — read each with
  `aeat app modelo work revision <work-unit-id> --format json` before
  starting the 180. Modelo 180 folds these four filings' casillas 02 (base)
  and 03 (retenciones) into its annual totals; a missing or stale quarter
  blocks verification (see below). Modelo 115 is quarterly-only, so there is
  no cadence ambiguity to confirm the way Modelo 111/190 requires.
- The `filing_year`. The period is always the annual token `0A` — Modelo 180
  has no quarterly variant.

## Procedure

1. Read the form shape: `aeat app modelo describe 180 --year <YEAR>
   --period 0A` and `aeat app modelo casillas 180 --year <YEAR> --period
   0A`. See the `reference/casillas.md` companion for what each casilla and
   the per-perceptor rows mean.
2. Create the work unit: `aeat app modelo work create --modelo 180 --year
   <YEAR> --period 0A`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries
   `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 180 adds over the annual-informativa pattern

- **Three declarante-level summary casillas**, folding the year's four
  Modelo 115 quarters:
  - **Casilla "Número total de perceptores"** — the DISTINCT count of
    landlords (perceptores) paid across the year, computed directly from the
    dedicated per-perceptor retención store (a `perceptor_count_distinct`
    fact), never a sum of the four quarters' Modelo 115 perceptor counts (a
    landlord paid in more than one quarter is not double-counted).
  - **Casilla "Base retenciones e ingresos a cuenta total"** — the year's
    four Modelo 115 casilla-02 totals (each quarter's taxable rental base)
    summed via a relation fold-in.
  - **Casilla "Retenciones e ingresos a cuenta total"** — the year's four
    Modelo 115 casilla-03 totals (each quarter's own retenciones) summed via
    a relation fold-in.
- **Per-perceptor detail rows are MANUAL, not ledger-derived.** Unlike
  Modelo 190 (whose per-perceptor rows are computed from the withholding
  store), Modelo 180's per-landlord rows — base and retenciones per
  perceptor, plus the landlord's identity, the leased inmueble's cadastral
  and address detail — are `input_kind = "manual"` in the registry. The
  declarante-level totals above are folded/computed automatically; the
  per-perceptor breakdown that must sum to those totals is NOT. Before
  export, confirm every landlord paid during the year has a corresponding
  manually-entered row, and that the per-perceptor base/retenciones rows sum
  to the declarante totals — a taxpayer who calculates only the
  declarante-level summary and skips the per-perceptor entry has an
  incomplete filing even though `calculate` reports `success`.
- **No en-especie or manual-block distinction on the declarante side.**
  Modelo 115 has a single ledger-aggregated block (unlike Modelo 111's
  nine); Modelo 180's declarante totals fold only that one concept. There is
  no separate manual-vs-ledger split to check on the declarante summary the
  way Modelo 190 must check Modelo 111's manual income blocks.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced).
- The annual declarante totals are consistent with the four quarters'
  declared Modelo 115 casillas 02/03; a nonzero perceptor count with a zero
  total base or zero total retenciones is the under-declaration shape to
  question before export.
- Every manually-entered per-perceptor row is present for every landlord
  paid during the year, and the per-perceptor base/retenciones figures sum
  to the declarante-level totals the CLI computed — a mismatch here is not
  caught by `calculate` and must be checked before relying on `verify`.
- Every reported casilla and per-perceptor row value is quoted verbatim
  from the JSON with its grounding.

## Verify and hand off

5. Verify independently: `aeat app modelo work verify <work-unit-id>
   --format json`. Modelo 180 verification is a blocking equality gate on
   the three declarante summary casillas: the annual perceptor count, base
   total, and retenciones total must each match the corresponding fold-in
   from the four Modelo 115 quarters within the registry's tolerance. It
   does NOT check that the manually-entered per-perceptor rows sum to those
   totals — that reconciliation is the operator's responsibility per the
   success assertions above. A `BLOCKING_RULE` finding on the declarante
   totals means a quarter is missing, stale, or was recalculated after 180
   was created — re-check each 115 quarter's revision before retrying, never
   edit the 180 declarante casilla to force a match. Treat exit `1` as a
   verdict; do not export a BLOCKED revision.
6. Export the local artefact: `aeat app modelo export <work-unit-id>`. It is
   NOT official AEAT evidence; the taxpayer uploads it in the AEAT portal.
7. After the human files, pull official evidence with
   `aeat app modelo reconcile pull`.
