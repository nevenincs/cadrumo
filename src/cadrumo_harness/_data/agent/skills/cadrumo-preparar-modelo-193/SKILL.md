---
name: cadrumo-preparar-modelo-193
description: >-
  Prepare a Modelo 193 (annual summary of retenciones on capital mobiliario)
  from the four calculated quarterly Modelo 123s: create the work unit,
  calculate the annual summary, verify it reconciles with the quarters, review
  the per-perceptor rows, export the local fichero-BOE and hand it to the
  taxpayer to file. Use when the taxpayer who withholds retención on capital
  income must file the annual Modelo 193.
applies_when:
  profile_facts:
    - fact: pays_capital_income_with_retencion
      match: is_true
---

# Prepare Modelo 193

Modelo 193 is the annual retenciones e ingresos a cuenta declaración
informativa for rendimientos del capital mobiliario: it does not compute a new
withholding result, it folds the year's four quarterly Modelo 123
self-assessments into annual totals and adds a per-perceptor breakdown (who was
paid what capital income, and how much was withheld from them). Cadrumo computes
and folds it; you run the steps and relay the result. Never compute a casilla
value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

Modelo 193 is to Modelo 123 what Modelo 190 is to Modelo 111 (see
`cadrumo-preparar-modelo-190`): an annual informativa that reconciles against
four already-filed quarterly self-assessments of the same retenciones tax
category, with a per-perceptor detail block. The lifecycle (work create,
calculate, verify, revision review, export, reconcile) is the same. The delta is
the source modelo (123, capital mobiliario, not 111, trabajo/actividades), the
declarante shape (two totals plus a count of perceptor records, not nine income
blocks), and the per-perceptor row content (a single clave per perceptor, not a
clave/subclave combination across nine income categories).

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows a session (`sign_in` or `key`). With `none`, ask the person to
  sign in to Cadrumo.
- A profile is active (`overview.status`, `aeat app overview status`).
- The ledger for the full `filing_year` is built and classified: every
  capital-income payment subject to retención carries its withholding scheme,
  rate, and perceptor identity across all four quarters (`ledger.check`,
  `aeat app ledger check`). If it is not, load `cadrumo-llevar-libro` and then
  `cadrumo-clasificar`.
- **All four Modelo 123 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated.** Find each quarter's work unit with
  `modelo.work.list` (`aeat app modelo work list`) and read it with
  `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
  <work-unit-id>`) before starting the 193. For ejercicio 2024, Modelo 193 folds
  these four filings' casilla `06` (base total) and casilla `09` (retenciones
  total) into its own annual totals via the `annual_summary` relation, so a
  missing or stale quarter blocks verification (see below); from 2025 the
  quarters are a reconciliation cross-check only. Confirm the taxpayer actually
  files Modelo 123 on quarterly cadence with `overview.explain` (`aeat app
  overview explain 123 --year <YEAR>`) before assuming it.
- The `filing_year`. The period is always the annual token `0A` — Modelo 193
  has no quarterly variant.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 193, `filing_year` and `period` `0A` (`aeat app modelo describe 193` and
   `aeat app modelo casillas 193`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla and the per-perceptor rows mean.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 193 --year <YEAR> --period 0A`). It creates, or reuses, the
   local work unit for that year and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger and, for
   2024, the four Modelo 123 quarters. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value. The per-perceptor rows are part of the
   `calculation`, with the same grounding.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## What Modelo 193 adds over the annual-informativa pattern

- **Three declarante-level summary casillas**, never re-summed by hand:
  - **Casilla "Numero total de perceptores"** — the number of type-2
    perceptor records the declaration carries, as every record design
    states: a perceptor on several records (several claves, or from 2025
    several ejercicios de devengo) counts once per record. It is not a sum
    of the quarters' perceptor counts and not a count of distinct NIFs.
  - **Casilla "Base retenciones e ingresos a cuenta total"** — for ejercicio
    2024, the year's four Modelo 123 casilla-`06` totals summed via an
    `annual_summary` relation; in the other supported years, the sum of the
    base field over the type-2 perceptor records.
  - **Casilla "Retenciones e ingresos a cuenta total"** — for ejercicio
    2024, the year's four Modelo 123 casilla-`09` totals summed via an
    `annual_summary` relation; in the other supported years, the sum of the
    retenciones field over the type-2 perceptor records.
- **Per-perceptor detail rows.** Unlike Modelo 390 (which has no row-level
  detail), Modelo 193 is an informativa: it reports one type-2 record per
  perceptor and clave (and, from 2025, ejercicio de devengo) — tax id, legal
  name, clave (the capital-income category code, e.g. intereses de cuentas,
  dividendos), the amount perceived (dinerario), and the retención practicada.
  These rows are ledger-derived from the same withholding store the
  declarante-level totals draw from; do not hand-construct or edit a perceptor
  row.
- **No manual-block distinction at this layer.** Every declarante total and
  every perceptor row on Modelo 193 is ledger-derived (the 2024 money totals
  through the Modelo 123 relation, everything else through the `withholding`
  binding source); there is no manual (non-ledger-derived) income block
  equivalent to Modelo 111's trabajo-en-especie or ganancias-forestales
  casillas. A suspicious `0` on any Modelo 193 total traces back to a missing
  perceptor record, or for 2024 to a Modelo 123 quarter that is missing, stale,
  or has an unclassified ledger entry — check the source, not the 193.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- The annual totals are consistent with the four quarters' declared
  Modelo 123 casillas `06` and `09`; a nonzero perceptor count with a zero
  total base or zero total retenciones is the under-declaration shape to
  question before export. The honest-declaration rule governs.
- Every reported casilla and per-perceptor row value is quoted verbatim
  from the result with its grounding.

## Verify and hand off

5. Verify with `modelo.work.verify` (`aeat app modelo work verify
   --work-unit-id <work-unit-id>`). It checks the saved draft against the
   requirements for being verified complete and records a verification report
   in the profile. A second run by you is not an independent check, so read the
   result itself: `completeness_status` is `complete`, `incomplete` or
   `blocked`, `granted_verificado_completo` says whether the revision was
   granted, and the findings are in `verification.report.findings`, each with its `kind`,
   `severity` (`blocking` or `warning`), `casilla_id`, `legal_refs` and
   `source_refs`. Modelo 193 verification is a **blocking equality gate**: the annual
   base total and retenciones total each must equal the corresponding total
   folded from the four Modelo 123 quarters. A finding of kind `blocking_rule`
   here means a quarter is missing, stale, or was recalculated after 193 was
   created — re-check each 123 quarter's revision before retrying, never edit
   the 193 casilla to force a match. Relay every finding. On the command line, exit `1` is a verdict, not
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
