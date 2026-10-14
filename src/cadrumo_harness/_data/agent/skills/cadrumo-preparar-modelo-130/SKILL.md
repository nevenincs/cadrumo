---
name: cadrumo-preparar-modelo-130
description: >-
  Prepare a Modelo 130 (IRPF quarterly instalment, estimación directa) from the
  built ledger: create the work unit, calculate, verify, export the local
  fichero-BOE and hand it to the taxpayer to file. Use when a self-employed
  individual under estimación directa needs the Modelo 130 for a quarter.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [directa_normal, directa_simplificada]
---

# Prepare Modelo 130

Modelo 130 is the quarterly IRPF instalment (pago fraccionado) for individuals
under direct estimation (estimación directa). Cadrumo computes it; you run the
steps and relay the result. Never compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows a session (`sign_in` or `key`). With `none`, ask the person to
  sign in to Cadrumo.
- A profile is active: `overview.status` (`aeat app overview status`) reports it.
- The ledger for the quarter is built and classified, with incoming and outgoing
  business transactions imported, IRPF categories and any business-use ratios
  applied: `ledger.status` and `ledger.check` (`aeat app ledger status`,
  `aeat app ledger check`). If it is not, load `cadrumo-llevar-libro` and then
  `cadrumo-clasificar`.
- You know the `filing_year` and the `period` (`1T`, `2T`, `3T` or `4T`).

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 130, `filing_year` and `period` (`aeat app modelo describe 130` and
   `aeat app modelo casillas 130`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla
   means.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 130 --year <YEAR> --period <PERIOD>`). It creates, or
   reuses, the local work unit for that quarter and sends nothing out. In the
   result, `outcome.kind` is `success` with the work unit under `unit`
   (`work_unit_id`), or `refused` with a `reason`. Report a refusal as it is; do
   not ask for the applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger and the
   profile. Read the result's `calculation_revision_id`, the `calculation`
   (`casilla_values`, `result_summary`, and `observations`, each with its
   `casilla_id`, `value`, `legal_refs` and `source_refs`) and `advisories`.
   Keep the grounding with every value.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- The rendimiento casilla (03) is consistent with the declared ingresos (01)
  minus gastos (02). If ingresos are positive but the partial result (07) is
  zero with no declared reduction, treat it as suspect and ask the taxpayer to
  confirm before going on; the honest-declaration rule governs.
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
   `source_refs`. Relay every finding. On the command line, exit `1` is a
   verdict, not a crash. Do not export a revision that verifies `blocked`.
6. When the revision verifies clean, tell the person you are about to export it
   and wait for their go-ahead in the conversation. Then export with
   `modelo.export` (`aeat app modelo export <work-unit-id>`). It writes a
   fichero-BOE to the `output_path` you give, which must be inside the
   conversation workspace, and never contacts the AEAT. Do not replace an
   existing file unless the person asks. The file is NOT official AEAT evidence
   and the return is NOT filed. Tell the taxpayer to upload it themselves in the
   AEAT portal.
7. After the person says they have filed, load `cadrumo-reconciliar`. Official
   evidence comes from `modelo.reconcile.pull` (`aeat app modelo reconcile
   pull`), which contacts the AEAT read-only to fetch the justificante and
   compare it with the saved calculation. It is never asserted from the local
   export.
