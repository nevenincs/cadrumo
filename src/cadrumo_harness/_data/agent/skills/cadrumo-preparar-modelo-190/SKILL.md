---
name: cadrumo-preparar-modelo-190
description: >-
  Prepare a Modelo 190 (annual summary of retenciones on work and economic
  activities) from the four calculated quarterly Modelo 111s: create the work
  unit, calculate the annual summary, verify it reconciles with the quarters,
  review the per-perceptor rows, export the local fichero-BOE and hand it to
  the taxpayer to file. Use when the taxpayer who withholds retención must
  file the annual Modelo 190.
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
informativa: it does not compute a new withholding result, it folds the year's
four quarterly Modelo 111 self-assessments into annual totals and adds a
per-perceptor breakdown (who was paid what, and how much was withheld from
them). Cadrumo computes and folds it; you run the steps and relay the result.
Never compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

Modelo 190 is to Modelo 111 what Modelo 390 is to Modelo 303 (see
`cadrumo-preparar-modelo-390`): an annual informativa that reconciles against
four already-filed quarterly self-assessments of the same tax category. The
lifecycle (work create, calculate, verify, revision review, export, reconcile)
is the same. The delta is the source modelo (111, not 303), the fold-in
mechanism (a direct `annual_summary` relation sum, not a separate
reconciliation-casilla block), and the addition of per-perceptor detail rows
that Modelo 390 has no equivalent of.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows a session (`sign_in` or `key`). With `none`, ask the person to
  sign in to Cadrumo.
- A profile is active (`overview.status`, `aeat app overview status`).
- The ledger for the full `filing_year` is built and classified: every withheld
  payment carries its withholding scheme, rate, and perceptor identity across
  all four quarters (`ledger.check`, `aeat app ledger check`). If it is not,
  load `cadrumo-llevar-libro` and then `cadrumo-clasificar`.
- **From ejercicio 2025, all four Modelo 111 quarters (`1T`, `2T`, `3T`,
  `4T`) for the same `filing_year` are already calculated.** Find each quarter's
  work unit with `modelo.work.list` (`aeat app modelo work list`) and read it
  with `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
  <work-unit-id>`) before starting the 190. If a quarter is missing, load
  `cadrumo-preparar-modelo-111`. From 2025 Modelo 190 folds these four filings'
  casillas 02/05/08/11/14/17/20/23/26/28 into its annual totals; a missing or
  stale quarter blocks verification (see below). Up to ejercicio 2024 the totals
  are the sums over the year's own perceptor records, as that year's record
  design states, and no Modelo 111 quarter is read. Confirm the taxpayer
  actually files Modelo 111 on quarterly cadence with `overview.explain` (`aeat
  app overview explain 111 --year <YEAR>`) before assuming it — the registry
  folds only the `1T`-`4T` quarterly tokens into Modelo 190; a monthly-cadence
  Modelo 111 filer is out of scope for this skill's automatic fold-in and needs
  the person's explicit attention.
- The `filing_year`. The period is always the annual token `0A` — Modelo 190
  has no quarterly variant.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 190, `filing_year` and `period` `0A` (`aeat app modelo describe 190` and
   `aeat app modelo casillas 190`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla and the per-perceptor rows mean.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 190 --year <YEAR> --period 0A`). It creates, or reuses, the
   local work unit for that year and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger and, from
   2025, the four Modelo 111 quarters. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value. The per-perceptor rows are part of the
   `calculation`, with the same grounding.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## What Modelo 190 adds over the annual-informativa pattern

- **Three declarante-level summary casillas**, never re-summed by hand. The
  two amounts fold the four Modelo 111 quarters via `annual_summary`
  relations from ejercicio 2025; up to 2024 they sum the perceptor
  records' percepciones and retenciones fields:
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

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- The annual totals are consistent with the four quarters' declared
  Modelo 111 casillas; a nonzero perceptor count with a zero total
  percepciones or zero total retenciones is the under-declaration shape to
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
   `source_refs`. Modelo 190 verification is a **blocking equality gate**: the annual
   perceptions count, perceptions amount, and retenciones amount each must equal
   the corresponding total folded from the four Modelo 111 quarters. A finding of
   kind `blocking_rule` here means a quarter is missing, stale, or was
   recalculated after 190 was created — re-check each 111 quarter's revision
   before retrying, never edit the 190 casilla to force a match. Relay every
   finding. On the command line, exit `1` is a verdict, not
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
