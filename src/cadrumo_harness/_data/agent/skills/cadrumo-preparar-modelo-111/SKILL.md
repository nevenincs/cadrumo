---
name: cadrumo-preparar-modelo-111
description: >-
  Prepare a Modelo 111 (retenciones e ingresos a cuenta del trabajo y de
  actividades económicas) from the classified ledger: create the work unit,
  calculate the quarterly or monthly withholding totals, verify, export the
  local fichero-BOE and hand it to the taxpayer to file. Use when the taxpayer
  withholds retención on salaries, professional fees, premios or derechos de
  imagen and needs the Modelo 111 for a period.
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
what it pays out and remits to the AEAT. Cadrumo computes it from the classified
ledger's withholding schemes; you run the steps and relay the result. Never
compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

This skill follows the same lifecycle as `cadrumo-preparar-modelo-303` (work
create, calculate, verify, revision review, export, reconcile). The delta is the
ledger-derivation mechanism (a per-scheme retenciones aggregation, not IVA
repercutido/soportado) and the period grammar (Modelo 111 accepts both quarterly
and monthly tokens).

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows a session (`sign_in` or `key`). With `none`, ask the person to
  sign in to Cadrumo.
- A profile is active (`overview.status`, `aeat app overview status`).
- The ledger for the period records every withheld payment with its withholding
  scheme and rate (`ledger.check`, `aeat app ledger check`). A payment lacking
  its scheme cannot be aggregated into casillas 01-03, 07-09, or 13-15 below. If
  the ledger is not ready, load `cadrumo-llevar-libro` and then
  `cadrumo-clasificar`.
- You know the `filing_year` and the `period`. Modelo 111 accepts either the
  quarterly tokens (`1T`-`4T`) or the monthly tokens (`01`-`12`). Confirm which
  cadence applies to this taxpayer with `overview.explain` (`aeat app overview
  explain 111 --year <YEAR>`) rather than assuming quarterly.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 111, `filing_year` and `period` (`aeat app modelo describe 111` and
   `aeat app modelo casillas 111`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla block means.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 111 --year <YEAR> --period <PERIOD>`). It creates, or reuses, the
   local work unit for that period and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger and the
   profile. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## What Modelo 111 adds over the quarterly IVA pattern

- **Three ledger-aggregated blocks.** Casillas 01-03 (rendimientos del trabajo
  dinerarios), 07-09 (rendimientos de actividades económicas dinerarios), and
  13-15 (premios dinerarios) are each bound to a `retenciones_aggregation`
  source: casilla `01`/`07`/`13` is the distinct perceptor count, the next
  casilla is the taxable-base sum, and the third is the retención-amount sum,
  each scoped to that block's withholding scheme(s)
  (`rendimientos_trabajo`/`rendimientos_trabajo_administrador` for casillas
  01-03; `actividades_economicas`/`actividades_profesionales` for casillas
  07-09; `premios` for casillas 13-15). These three are the ones Cadrumo
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
  year's Modelo 111 filings, see `cadrumo-preparar-modelo-190`) folds every
  quarter's casillas 02/05/08/11/14/17/20/23/26/28 into its own annual totals
  via cross-modelo relations. Do not prepare Modelo 190 until all of the
  year's Modelo 111 periods are calculated and stable - a quarter recalculated
  afterward invalidates the annual figure the same way a stale Modelo 303
  quarter invalidates Modelo 390.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- Casilla 28 (total retenciones) is consistent with the sum of casillas 03,
  06, 09, 12, 15, 18, 21, 24, and 27 reported in the revision; a nonzero
  perceptor count (01/07/13) with a zero base or zero retención sum on the
  same block is the under-declaration shape to question before export. The
  honest-declaration rule governs.
- Every reported casilla value is quoted verbatim from the result, with its
  `legal_refs` and `source_refs`.

## Verify and hand off

5. Verify with `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft against the
   requirements for being verified complete and records a verification report
   in the profile. A second run by you is not an independent check, so read the
   result itself: `completeness_status` is `complete`, `incomplete` or
   `blocked`, `granted_verificado_completo` says whether the revision was
   granted, and the findings are in `verification.report.findings`, each with its `kind`,
   `severity` (`blocking` or `warning`), `casilla_id`, `legal_refs` and
   `source_refs`. Relay every finding. On the command line, exit `1` is a verdict, not
   a crash. Do not export a revision that verifies `blocked`.
6. When the revision verifies clean, tell the person you are about to export it
   and wait for their go-ahead in the conversation. Then export with
   `modelo.export` (`aeat app modelo export <work-unit-id>`). It writes a fichero-BOE to the
   `output_path` you give, which must be inside the conversation workspace, and
   never contacts the AEAT. Do not replace an existing file unless the person
   asks. The file is NOT official AEAT evidence and the return is NOT filed. Tell
   the taxpayer to upload it themselves in the AEAT portal.
7. After the person says they have filed, load `cadrumo-reconciliar`. Official
   evidence comes from `modelo.reconcile.pull` (`aeat app modelo reconcile
   pull`), which contacts the AEAT read-only to fetch the justificante and
   compare it with the saved calculation. It is never asserted from the local
   export.
