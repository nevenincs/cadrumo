---
name: cadrumo-preparar-modelo-115
description: >-
  Prepare a Modelo 115 (retenciones e ingresos a cuenta sobre alquileres de
  inmuebles urbanos) from the classified ledger: create the work unit,
  calculate the quarterly withholding totals, verify, export the local
  fichero-BOE and hand it to the taxpayer to file. Use when the taxpayer
  withholds retención on rent it pays for a local de negocio or other urban
  premises and needs the Modelo 115 for a quarter.
applies_when:
  profile_facts:
    - fact: pays_rent_with_retencion
      match: is_true
---

# Prepare Modelo 115

Modelo 115 is the quarterly self-assessment of retenciones e ingresos a cuenta
that a retenedor (a business paying rent on an urban premises it leases - a
local de negocio, an office) withholds from the rent it pays and remits to the
AEAT. Cadrumo computes it from the classified ledger's withholding schemes; you
run the steps and relay the result. Never compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

This skill follows the same lifecycle and ledger-aggregation mechanism as
`cadrumo-preparar-modelo-111`. The deltas are: (1) Modelo 115 has a single
ledger-aggregated block, not three or nine, (2) Modelo 115 is quarterly only -
it has no monthly cadence to confirm, and (3) Modelo 115's annual roll-up is
Modelo 180, not Modelo 190.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows an admitted session (`attended` or `key`). With `none`, ask
  the person to hold a live Cadrumo session and review this server's exact
  attendance request, or configure a separately reviewed key. A sign-in alone
  does not grant this server access.
- A profile is active (`overview.status`, `aeat app overview status`).
- The ledger for the quarter records every rent payment the taxpayer made on a
  leased urban premises, with its withholding scheme and rate (`ledger.check`,
  `aeat app ledger check`). A payment lacking its scheme cannot be aggregated
  into casillas 01-02 below. If the ledger is not ready, load
  `cadrumo-llevar-libro` and then `cadrumo-clasificar`.
- You know the `filing_year` and the `period`. Modelo 115 accepts only the
  quarterly tokens (`1T`-`4T`) - confirm this with `overview.explain` (`aeat app
  overview explain 115 --year <YEAR>`) rather than assuming a monthly cadence
  carries over from Modelo 111.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 115, `filing_year` and `period` (`aeat app modelo describe 115` and
   `aeat app modelo casillas 115`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla means.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 115 --year <YEAR> --period <PERIOD>`). It creates, or reuses, the
   local work unit for that quarter and sends nothing out. In the result,
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

## What Modelo 115 changes from the retenciones pattern

- **One ledger-aggregated block, not several.** Casillas 01 (número de
  perceptores) and 02 (base de retenciones e ingresos a cuenta) are each
  bound to a `retenciones_aggregation` source scoped to the urban-rental
  withholding scheme: casilla 01 is the distinct perceptor (landlord) count,
  casilla 02 is the taxable-base sum. Unlike Modelo 111's nine blocks,
  Modelo 115 has no en-especie or manual-input income block - every
  perceptor and every euro of base the form declares comes from the ledger.
- **Casilla 03** ("Retenciones e ingresos a cuenta") is computed: 19% of
  casilla 02 (`irpf.urban_rental_withholding_rate`, currently 19%, LIRPF art.
  101/RD 439/2007 art. 100 and 108). Reach it through calculate, never by
  re-deriving the percentage.
- **Casilla 04** ("Resultado de anteriores declaraciones") is the one manual
  field: a same-year prior-quarter correction the taxpayer supplies when
  amending. It is not cross-period carried; do not assume it defaults to
  zero without asking whether an amendment applies.
- **Casilla 05** (result to pay) is casilla 03 minus casilla 04.
- **Annual roll-up is Modelo 180, not Modelo 190.** Modelo 180 (the annual
  informativa summarising the year's Modelo 115 filings, see
  `cadrumo-preparar-modelo-180`) folds every quarter's casillas 02 and 03 into
  its own annual base and retenciones totals via cross-modelo relations, and
  independently derives its own DISTINCT perceptor-NIF count (not a sum of the
  quarterly counts, which would double-count a landlord paid in more than one
  quarter). Do not prepare Modelo 180 until all four quarters of Modelo 115 for
  the year are calculated and stable - a quarter recalculated afterward
  invalidates the annual figure the same way a stale Modelo 303 quarter
  invalidates Modelo 390.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- Casilla 03 (retenciones) is consistent with 19% of casilla 02 (base) as
  reported in the revision; a nonzero perceptor count (01) with a zero base or
  zero retención sum (02/03) is the under-declaration shape to question before
  export. The honest-declaration rule governs.
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
