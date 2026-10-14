---
name: cadrumo-preparar-modelo-180
description: >-
  Prepare a Modelo 180 (annual summary of retenciones on urban-premises rent)
  from the four calculated quarterly Modelo 115s: create the work unit,
  calculate the annual summary, check the per-landlord rows, verify, export
  the local fichero-BOE and hand it to the taxpayer to file. Use when the
  taxpayer who withholds retención on rent must file the annual Modelo 180.
applies_when:
  profile_facts:
    - fact: pays_rent_with_retencion
      match: is_true
---

# Prepare Modelo 180

Modelo 180 is the annual retenciones e ingresos a cuenta declaración
informativa for urban-premises rental: it does not compute a new withholding
result, it folds the year's four quarterly Modelo 115 self-assessments into
annual totals and adds a per-perceptor breakdown (which landlord was paid what,
and how much was withheld from them). Cadrumo computes and folds it; you run the
steps and relay the result. Never compute a casilla value yourself.

Each step below names the registered operation that does the work and, in
brackets, the `aeat` command that is the same step on the command line. Through
the tool server, read the operation's contract and input schema with `describe`,
submit it with `execute`, and read the settled `result`. Before a step runs, say
in a sentence what it does: every call and every program start is put to the
person for approval.

Modelo 180 is to Modelo 115 what Modelo 190 is to Modelo 111 (see
`cadrumo-preparar-modelo-190`): an annual informativa that reconciles against
four already-filed quarterly self-assessments of the same withholding concept.
The lifecycle (work create, calculate, verify, revision review, export,
reconcile) is the same. The delta is the source modelo (115, not 111), the
narrower fold-in (a single ledger-aggregated block, not up to nine income
blocks), and — the load-bearing difference — Modelo 180's per-perceptor detail
rows are **manual input**, not ledger-derived like Modelo 190's.

## Preconditions

Confirm these before you start. If one is missing, say what is missing and stop
that step.

- `status` shows an admitted session (`attended` or `key`). With `none`, ask
  the person to hold a live Cadrumo session and review this server's exact
  attendance request, or configure a separately reviewed key. A sign-in alone
  does not grant this server access.
- A profile is active (`overview.status`, `aeat app overview status`).
- **All four Modelo 115 quarters (`1T`, `2T`, `3T`, `4T`) for the same
  `filing_year` are already calculated.** Find each quarter's work unit with
  `modelo.work.list` (`aeat app modelo work list`) and read it with
  `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
  <work-unit-id>`) before starting the 180. If a quarter is missing, load
  `cadrumo-preparar-modelo-115`. Modelo 180 folds these four filings' casillas
  02 (base) and 03 (retenciones) into its annual totals; a missing or stale
  quarter blocks verification (see below). Modelo 115 is quarterly-only, so
  there is no cadence ambiguity to confirm the way Modelo 111/190 requires.
- The `filing_year`. The period is always the annual token `0A` — Modelo 180
  has no quarterly variant.

## Procedure

1. Read the form shape so you cite real casillas, not remembered ones: the
   `authority` tool with `query` `describe` and then `casillas`, giving
   `modelo` 180, `filing_year` and `period` `0A` (`aeat app modelo describe 180` and
   `aeat app modelo casillas 180`, each with `--year` and `--period`). Both read
   bundled public data. `reference/casillas.md` explains what each casilla and the per-perceptor rows mean.
2. Create the work unit with `modelo.work.create` (`aeat app modelo work
   create --modelo 180 --year <YEAR> --period 0A`). It creates, or reuses, the
   local work unit for that year and sends nothing out. In the result,
   `outcome.kind` is `success` with the work unit under `unit` (`work_unit_id`),
   or `refused` with a `reason`. Report a refusal as it is; do not ask for the
   applicability check to be bypassed unless the person asks.
3. Calculate with `modelo.work.calculate` (`aeat app modelo work calculate
   <work-unit-id>`). It saves a new draft calculation, folding in the four
   Modelo 115 quarters. Read the result's `calculation_revision_id`, the `calculation` (`casilla_values`,
   `result_summary`, and `observations`, each with its `casilla_id`, `value`,
   `legal_refs` and `source_refs`) and `advisories`. Keep the grounding with
   every value.
4. To read the computed revision again without recalculating, use
   `modelo.work.revision` (`aeat app modelo work revision --work-unit-id
   <work-unit-id>`). This is the value set you report to the taxpayer.

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
- **Per-perceptor detail rows.** Each landlord's base (`perc.base`) and
  retenciones (`perc.retenciones`) are bound from the withholding store, one
  row per type-2 record (`modelo-180-perceptor-row-base`,
  `modelo-180-perceptor-row-retenciones`). The landlord's identity and the
  leased inmueble's cadastral and address detail are manual; list the manual
  casillas with the `authority` tool's `casillas` query. Check that the rows
  sum to the declarante totals above. Before export, confirm every landlord
  paid during the year appears as a row. A missing landlord means the
  withholding store lacks that payment: record it in the ledger (load
  `cadrumo-llevar-libro`) and recalculate; never invent a row. Ask the person
  for each landlord's identity and inmueble detail, and enter them through the
  inputs `modelo.work.calculate` accepts (read its input schema with
  `describe`).
- **No en-especie or manual-block distinction on the declarante side.**
  Modelo 115 has a single ledger-aggregated block (unlike Modelo 111's
  nine); Modelo 180's declarante totals fold only that one concept. There is
  no separate manual-vs-ledger split to check on the declarante summary the
  way Modelo 190 must check Modelo 111's manual income blocks.

## Success assertions

Before handing off, confirm in the calculate or revision result:

- The operation settled successfully. An operation that settled refused or
  failed has no result, so read `error_detail`. On the command line with `--format json`, the
  envelope `status` is `success`, or `warning` with every notice surfaced to the
  taxpayer, and never `error`.
- The annual declarante totals are consistent with the four quarters'
  declared Modelo 115 casillas 02/03; a nonzero perceptor count with a zero
  total base or zero total retenciones is the under-declaration shape to
  question before export. The honest-declaration rule governs.
- Every manually-entered per-perceptor row is present for every landlord
  paid during the year, and the per-perceptor base/retenciones figures sum
  to the declarante-level totals Cadrumo computed — a mismatch here is not
  caught by the calculation and must be checked before relying on verify.
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
   `source_refs`. Modelo 180 verification is a blocking equality gate on the three
   declarante summary casillas: the annual perceptor count, base total, and
   retenciones total must each match the corresponding fold-in from the four
   Modelo 115 quarters within the registry's tolerance. It does NOT check that
   the manually-entered per-perceptor rows sum to those totals — that
   reconciliation is yours, per the success assertions above. A finding of kind
   `blocking_rule` on the declarante totals means a quarter is missing, stale,
   or was recalculated after 180 was created — re-check each 115 quarter's
   revision before retrying, never edit the 180 declarante casilla to force a
   match. Relay every finding. On the command line, exit `1` is a verdict, not
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
