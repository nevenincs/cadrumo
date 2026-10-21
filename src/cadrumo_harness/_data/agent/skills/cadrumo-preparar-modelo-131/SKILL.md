---
name: cadrumo-preparar-modelo-131
description: >-
  Prepare a Modelo 131 (IRPF quarterly instalment, estimación objetiva /
  módulos) from the ledger and the taxpayer's módulos figures: create the work
  unit, calculate, verify, export the local fichero-BOE and hand it to the
  taxpayer to file. Use when a self-employed individual under módulos needs the
  Modelo 131 for a quarter.
applies_when:
  profile_facts:
    - fact: irpf_income_categories
      match: contains
      values: [actividad_economica]
    - fact: irpf_estimation_regime
      match: equals
      values: [objetiva]
---

# Prepare Modelo 131

Modelo 131 is the quarterly IRPF instalment (pago fraccionado) for individuals
under objective estimation (estimación objetiva / módulos) — the counterpart of
Modelo 130 (estimación directa). Cadrumo computes it; you run the steps and
relay the result. Never compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows an admitted session (`attended` or `key`). With `none`, ask
  the person to hold a live Cadrumo session and review this server's exact
  attendance request, or configure a separately reviewed key. A sign-in alone
  does not grant this server access.
- A profile is active (`overview.status`, `aeat app overview status`) and its
  `irpf_estimation_regime` is objetiva; `cadrumo-autonomo-modulos` owns that
  gating predicate.
- The ledger for the quarter is built and classified, with incoming and outgoing
  business transactions imported (`ledger.status` and `ledger.check`,
  `aeat app ledger status`, `aeat app ledger check`). If it is not, load
  `cadrumo-llevar-libro` and then `cadrumo-clasificar`. Módulos rendimiento is
  NOT derived from the ledger — it is fixed by the annual Orden de módulos
  tables — but IVA and expense evidence for the same activity still needs a
  classified ledger.
- You know the `filing_year` and the `period` (`1T`, `2T`, `3T` or `4T`).
- The taxpayer's módulos figures for the period are at hand: the datos-base
  rendimiento (casilla 01) and, where applicable, the sin-datos-base volumen de
  ventas (casilla 03). These come from the taxpayer's own módulos worksheet
  against the year's Orden de módulos, not from the ledger and not from you. Ask
  for them if they are missing. The agrarian volumen de ingresos (casilla 05) is
  bound from the ledger's agrarian income (`modelo-131-volumen-ingresos-agrario`);
  if a calculation leaves it blank, ask the person.

## Procedure

1. Read the form shape for the exact filing year so you cite real casillas, not
   remembered ones — the casilla set and which casillas are computed vs manual
   CAN differ by revision year: the `authority` tool with `query` `describe` and
   then `casillas`, giving `modelo` 131, `filing_year` and `period` (`aeat app
   modelo describe 131` and `aeat app modelo casillas 131`, each with `--year`
   and `--period`). Both read bundled public data. `reference/casillas.md`
   explains what each casilla means and the revision-year delta.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 131 --year <YEAR> --period <PERIOD>`). It creates, or
   reuses, the local work unit for that quarter and sends nothing out. In the
   result, `outcome.kind` is `success` with the work unit under `unit`
   (`work_unit_id`), or `refused` with a `reason`. Report a refusal as it is; do
   not ask for the applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation from the ledger, the
   profile and the manual casilla values you give it; read its input schema with
   `describe`, and list the manual casillas with the `authority` tool's
   `casillas` query and `input_kind` `manual`. Read the result's
   `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- **The flagship under-declaration risk on this modelo**: casilla `01` ("Suma de
  rendimientos netos") is a manual módulos input because the rendimiento is
  determined externally (the Orden de módulos tables), not by the engine. A
  positive `01` MUST carry a positive `02` ("Pago fraccionado previo por
  datos-base"). The registry carries an advisory rule for exactly this check
  (`implies_nonzero` on `01` and `02`); it surfaces as a finding of kind
  `advisory`. If `01` is positive and `02` (or the final result `15`) is zero
  with no declared reduction, treat it as suspect and confirm with the taxpayer
  before going on. Do not export.
- Casilla `10` ("Diferencia") gates casilla `11` ("Resultados negativos de
  trimestres anteriores"): the registry's blocking rule `c11-cap-by-c10` refuses
  a calculation where `11` exceeds a strictly positive `10`. A verify that
  blocks on it means the prior-quarter negative carry is overstated; do not
  override it.
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
   `source_refs`. Relay every finding, including advisories: they are not
   errors, but they are never silently dropped. On the command line, exit `1` is
   a verdict, not a crash. Do not export a revision that verifies `blocked`.
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
