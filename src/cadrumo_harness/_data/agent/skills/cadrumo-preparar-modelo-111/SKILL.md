---
name: cadrumo-preparar-modelo-111
description: >-
  Prepare a Modelo 111 (retenciones e ingresos a cuenta del trabajo y de
  actividades económicas) from a classified ledger: create the work unit,
  calculate the quarterly (or monthly) withholding totals, verify, export the
  fichero-BOE, and hand off for the taxpayer to file. Use when the taxpayer
  withholds retención on salaries paid to employees, professional fees paid to
  autónomos, or premios/derechos de imagen subject to retención.
applies_when:
  profile_match: any
  profile_facts:
    - fact: has_employees
      match: is_true
    - fact: pays_professionals_with_retencion
      match: is_true
---

# Prepare Modelo 111

Modelo 111 is the periodic self-assessment of retenciones e ingresos a cuenta
that a retenedor (an employer or a payer of professional fees) withholds from
what it pays out and remits to the AEAT. The CLI computes it from the
classified ledger's withholding schemes; you orchestrate and relay. Never
compute a casilla value yourself.

This skill diffs against `cadrumo-preparar-modelo-303`: the lifecycle spine (work
create → calculate → verify → revision review → export → reconcile) is
identical. The delta is the ledger-derivation mechanism (a per-scheme
retenciones aggregation, not IVA repercutido/soportado) and the period grammar
(Modelo 111 accepts both quarterly and monthly tokens).

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- The ledger for the period records every withheld payment with its
  withholding scheme and rate: `aeat app ledger check`. A payment lacking its
  scheme cannot be aggregated into casillas 01-03, 07-09, or 13-15 below.
- You know the `filing_year` and the `period`. Modelo 111 accepts either the
  quarterly tokens (`1T`-`4T`) or the monthly tokens (`01`-`12`) - confirm
  which cadence applies to this taxpayer via
  `aeat app overview explain 111 --year <YEAR>` rather than assuming quarterly.

## Procedure

1. Read the form shape: `aeat app modelo describe 111 --year <YEAR>
   --period <PERIOD>` and `aeat app modelo casillas 111 --year <YEAR>
   --period <PERIOD>`. See the `reference/casillas.md` companion for what each
   casilla block means.
2. Create the work unit: `aeat app modelo work create --modelo 111 --year
   <YEAR> --period <PERIOD>`.
3. Calculate: `aeat app modelo work calculate <work-unit-id> --format json`.
   Read `result` and `notices`; every casilla carries
   `legal_refs`/`source_refs`.
4. Read the computed revision: `aeat app modelo work revision <work-unit-id>
   --format json`.

## What Modelo 111 adds over the quarterly IVA pattern

- **Three ledger-aggregated blocks.** Casillas 01-03 (rendimientos del trabajo
  dinerarios), 07-09 (rendimientos de actividades económicas dinerarios), and
  13-15 (premios dinerarios) are each bound to a `retenciones_aggregation`
  source: casilla `01`/`07`/`13` is the distinct perceptor count, the next
  casilla is the taxable-base sum, and the third is the retención-amount sum,
  each scoped to that block's withholding scheme(s)
  (`rendimientos_trabajo`/`rendimientos_trabajo_administrador` for casillas
  01-03; `actividades_economicas`/`actividades_profesionales` for casillas
  07-09; `premios` for casillas 13-15). These three are the ones the CLI
  computes from the classified ledger.
- **The remaining blocks are manual, not silently zero by design.** Casillas
  04-06 (trabajo en especie), 19-27 (ganancias patrimoniales forestales,
  cesión de derechos de imagen) have no ledger binding in the registry and are
  reported by the taxpayer directly; they read `0` only when genuinely absent
  for the period, never as an artefact of an unclassified ledger entry. If the
  taxpayer describes a payment that should land in one of these blocks, ask
  where it is recorded before treating the calculated `0` as final.
- **Casilla 28** ("Total retenciones e ingresos a cuenta") sums casillas 03,
  06, 09, 12, 15, 18, 21, 24, and 27 across every block - dinerario and en
  especie alike, not just the three ledger-aggregated ones.
- **Casilla 30** (result to pay) is casilla 28 minus casilla 29 ("Resultado de
  anteriores autoliquidaciones", a same-year prior-quarter/month correction
  the taxpayer supplies when amending).
- **Annual roll-up.** Modelo 190 (the annual informativa summarising the
  year's Modelo 111 filings) folds every quarter's casillas 02/05/08/11/14/17/
  20/23/26/28 into its own annual totals via cross-modelo relations. Do not
  prepare Modelo 190 until all of the year's Modelo 111 periods are calculated
  and stable - a quarter recalculated afterward invalidates the annual figure
  the same way a stale Modelo 303 quarter invalidates Modelo 390.

## Success assertions

- `status` is `success` (or `warning` with every warning surfaced to the
  taxpayer), never `error`.
- Casilla 28 (total retenciones) is consistent with the sum of casillas 03,
  06, 09, 12, 15, 18, 21, 24, and 27 reported in the revision; a nonzero
  perceptor count (01/07/13) with a zero base or zero retención sum on the
  same block is the under-declaration shape to question before export (see
  `cadrumo-operator-grounding`).
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
