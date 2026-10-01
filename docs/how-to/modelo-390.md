(prepare-the-annual-modelo-390-iva-summary)=
# Prepare the annual Modelo 390 VAT summary

Use this guide when the active profile must prepare Modelo 390, the annual
Impuesto sobre el Valor Añadido (VAT) summary. Modelo 390 is an annual return,
but part of its review depends on the same year's periodic Modelo 303 VAT
self-assessments.

Cadrumo does not submit Modelo 390 to the Agencia Estatal de Administración
Tributaria (AEAT). Export creates a local fichero-BOE file, but its envelope
carries Cadrumo's all-zero development software identity, so AEAT does not
accept it. Read the calculated values back and enter them through the official
AEAT channel yourself.

## The filing task

Modelo 390 is the annual summary of your quarterly VAT filings. To prepare it:

1. Prepare and review the four quarterly Modelo 303 periods first.
2. Create a Modelo 390 draft for the annual period (`--period 0A`).
3. Calculate the annual summary from your year's records and the 303 values.
4. Review the calculated totals against your quarterly records.
5. Check that the draft is complete.
6. Export the annual file for review.
7. Enter the figures at the AEAT portal yourself and keep the AEAT receipt.

Not every taxpayer files Modelo 390. AEAT exonerates taxpayers included in the
Suministro Inmediato de Información (SII), and quarterly filers taxed only in
territorio común whose activity is under the régimen simplificado, the rental
of urban property, or both. They report their annual
operations in the Modelo 303 for the last period instead - see the AEAT guide to
the
[exoneration from Modelo 390](https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-gran-empresa/se-declara-volumen-operaciones/obligados-presentar-modelo-303/exonerados-presentacion-modelo-390.html).
The Modelo 303 for the last period of the year (`4T`, or `12` for monthly
filers) needs a confirmation that the exemption does not apply. Create it with
`aeat app modelo work attest-m303-exonerado-390`, passing the year, the last
period (`--period 4T`), and the moment you checked the conditions
(`--observed-at`).
Then pass the identifier and SHA-256 it prints to `work calculate` as
`--m303-exonerado-390-attachment-id` and `--m303-exonerado-390-sha256`.

The rest of this guide walks through these steps with the checks each one
needs. To understand how the tool organises the filing work behind the
commands, read
[The filing workflow](filing-spine.md)
after this guide.

(create-calculate-and-verify-the-annual-draft)=
## Create, calculate, and check the annual draft

**Requirement:** a valid taxpayer profile. Create one with `aeat config profile
create <name>`. See [Set up your taxpayer profile](profile-setup.md).

The example starts with the four 2025 Modelo 303 quarters recorded as filed, so the annual summary can fold them in. It then creates the Modelo 390 draft for 2025, calculates it, and checks it. The example uses 2025 because the annual return needs the year's four quarters already recorded as filed:

```{cli-sequence} modelo-390-annual-2025
:verify: Confirm the annual summary passed the check before you export it.
```

The check passes the draft as complete and reports issues that do not block filing: the four quarters are recorded as filed but carry no AEAT receipt yet, so the tool discloses that the annual reconciliation rests only on filings recorded in Cadrumo. That disclosure is correct - a quarter recorded as filed is honest proof for the annual fold-in, and the issue tells you where an AEAT receipt would strengthen the record. In this example the four quarters charged 1470.00 of VAT between them (420 + 315 + 210 + 525) and the year carries 105.00 of deductible input VAT (one purchase with a supporting document, 500 base at 21%), so the annual cuota devengada is 1470.00, the deducible total is 105.00, and the régimen-general result is 1365.00 (1470.00 − 105.00) - the full annual VAT equation, each figure matching the sum of the quarters (the reconciliation invariant). Input VAT counts only once the purchase has the invoice linked as a supporting document. The rest of this guide explains each stage and the checks around it.

## Setup steps before you start

Start with the local filing context:

- [Set up your taxpayer profile](profile-setup.md) and check the active profile.
- Check the census facts in your profile first with
  [Maintain Modelo 036 census facts in your profile](censo-update.md).
- Use [Plan your filing calendar](filing-calendar.md) to confirm the annual
  filing window.
- Confirm the annual period code with
  {ref}`Period codes and dates <period-tokens-and-dates>`.
  Modelo 390 uses `--period 0A`.
- [Import or add your transactions](import-bank-statements.md), then [classify
  them](classify-transactions.md). The annual totals from your records depend on
  the active profile's classified VAT entries.
- Prepare the same year's Modelo 303 periods first. Standard quarterly profiles
  use `1T`, `2T`, `3T`, and `4T`; monthly VAT-liquidation cases need extra review
  because the current Modelo 390 is set up against the quarterly 303 periods.
- Finish the Modelo 303 review path before relying on its values. See
  [Prepare a Modelo 303 VAT filing](modelo-303.md).

Modelo 390 combines two kinds of values:

- annual VAT totals from your records for the full filing year (source
  `ledger_iva_aggregation`)
- values taken from the same year's 303 quarters (source `relation_prefill`,
  reported by the check's issues as `origin=registry_relation`), where the tax
  rules name the 303 boxes and periods that feed the annual summary

The values taken from 303 depend on each quarter's recorded filing or AEAT receipt. The check blocks until one is present (see "What each Modelo 303 quarter needs before you check" below). The CLI does not guarantee that the history AEAT holds is current, read, or reconciled.

The rules that fill Modelo 390's boxes include 303 quarter sums for annual devengada, deducible, and régimen general result reconciliation. They also include compensation values copied or summed from the same year's 303 periods.

(what-each-modelo-303-quarter-needs-before-you-verify)=
## What each Modelo 303 quarter needs before you check

The Modelo 390 check depends on the four quarterly Modelo 303 returns. `work
calculate` for Modelo 390 produces a draft, but `work verify` blocks with
`cross_period_dependency_unclean` issues that block filing until each 303 quarter
(`1T`, `2T`, `3T`, `4T`) has a recorded filing or an AEAT receipt. A calculated or
checked 303 draft is not enough: the check reports `blockers=missing_observation,
missing_current_filing_record` for every quarter with no recorded filing.

Establish each quarter's filing status one of two ways before you check Modelo
390.

The first way is to record each 303 quarter as filed, while its AEAT filing-obligation window is open. Prepare and check each quarter (see [Prepare a Modelo 303 VAT filing](modelo-303.md)), then record each filing, repeating for `1T`, `2T`, `3T`, and `4T`. `work file` only records the filing in Cadrumo; it does not submit to AEAT, and it refuses outside the obligation window:

```{cli-sequence} modelo-390-file-quarter
```

The second way is to read or reconcile the official AEAT receipt for each quarter.
`live filed pull-sources` reads your filed declarations from AEAT and refuses when
AEAT authentication is not set up (it needs a Cl@ve identity matching the active
profile), so it is a live read shown as an example that is not run. `reconcile
import` reads a local AEAT receipt PDF and never contacts AEAT, but it needs the
real receipt:

```{cli-sequence} modelo-390-external-evidence
```

If you cannot establish a quarter's filing status, do not force the annual return past the block. Fix the missing 303 filing record or AEAT receipt first, or report the gap.

(check-each-visible-filing-target)=
## Check each filing target

Use the same active profile for every command. Inspect the four 303 filing targets
before you work on the annual target, repeating the `work status` check for each
of `1T`, `2T`, `3T`, and `4T`, and list all saved declarations with `work list` to
see all your filings (the inspect sequence under "Inspect the annual declaration"
below runs `work list` and the annual `work status`).

No command switches a current filing target for you. To move from one quarter
to another, change `--period`. To move from the quarterly 303 review to the
annual 390 review, change both `--modelo` and `--period`.

## Review the 303 values that feed Modelo 390

For each Modelo 303 period, list its saved calculations and inspect the one recorded as filed. These reads need the year's 303 quarters recorded as filed, so they are shown as examples that are not run. If no calculation recorded as filed exists locally, inspect the current or checked calculation instead with `--select latest-verified` or `--select current`:

```{cli-sequence} modelo-390-review-303
```

Repeat that review for `2T`, `3T`, and `4T`. Pay attention to the values that
Modelo 390 reconciles from Modelo 303:

- `iva.cuota-devengada-total`
- `iva.cuota-deducible-total`
- `iva.resultado-regimen-general`
- `iva.compensacion-generada-periodo`

If a 303 return was filed outside Cadrumo, read or reconcile the official AEAT data before you rely on local values, with the `live filed pull-sources` or `reconcile import` commands shown under [What each Modelo 303 quarter needs](#what-each-modelo-303-quarter-needs-before-you-verify) above. Reading filed declarations from AEAT is read-only; reconciliation reads the AEAT receipt or declaration file you supply. Modelo 390 calculation does not require a fresh check against what AEAT holds before it runs.

For VAT compensation history, use the VAT wallet commands; they support the compensation carry-forward review but are not a general Modelo 390 reconciliation gate. Inspect the balance with the `iva-wallet balance` step in the inspection example. Seed an opening balance, fix a wrong seed, or review the AEAT-side history with the following commands. The seed runs. Correcting a seed is refused once a 303 recorded as filed has consumed it, and the history read reaches AEAT, so those two are examples that are not run:

```{cli-sequence} modelo-390-wallet
:verify: Confirm the opening compensation balance seeds.
```

`pull-history` requires both `--from-year` and `--to-year`; it reads filed
Modelo 303 history from AEAT and refuses when AEAT authentication is not
configured. Use `seed` only when you have a real opening compensation balance
from before the local Modelo 303 history.

(inspect-the-annual-work-unit)=
## Inspect the annual declaration

Check the saved annual declaration: its boxes, its formulas, and the values Cadrumo fills in (`bindings`). Add `--missing` to that listing to focus on unfilled fields. The following example creates the annual draft and inspects its structure; the full-value chain that folds in the four quarters recorded as filed is the "Create, calculate, and check" example:

```{cli-sequence} modelo-390-inspect
:verify: Confirm the annual declaration's inputs and formulas read back.
```

That listing shows totals from your records (source `ledger_iva_aggregation`) and values taken from 303 (source `relation_prefill`, their ids prefixed `modelo-390-prev-303-`). Treat the values taken from 303 as figures that must be reviewed against the earlier 303 periods. Do not assume `work calculate` scans every local 303 declaration, every saved calculation, or every recorded filing automatically.

## Supply reviewed 303-derived values if needed

Check the annual period's records before calculation with the `ledger preflight` and `ledger status` steps in the inspection example.

The annual calculation uses your records for the whole year for the VAT totals in Modelo 390. For values taken from 303, the tax rules define the ids of the values Cadrumo fills in and their source periods. If those values are not already available to the calculation, inspect the list of missing values and supply reviewed values explicitly. The reviewed sums come from your own 303 review. The following example passes the ones this guide's year produces (1470.00 devengada, 105.00 deducible, 1365.00 régimen general), which match the annual totals from your records, and the reconciliation boxes carry the supplied figures:

```{cli-sequence} modelo-390-supply-binding
:verify: Confirm the supplied 303-derived values land on the annual reconciliation boxes.
```

Use reviewed numbers, not placeholders. If the reviewed 303 history is missing or inconsistent, stop and fix the 303 filing records or AEAT receipts before continuing. For review box by box and how values are filled in, see [Review and supply calculation inputs](review-calculation-values.md).

## Review the annual calculation

Inspect the saved annual calculations with the `work revisions` and `work revision` steps in the inspection example.

Compare the annual totals with the 303 reconciliation values:

- `iva.anual.cuota-devengada-total` should be reviewed against
  `iva.anual.reconciliacion.devengada-303`.
- `iva.anual.cuota-deducible-total` should be reviewed against
  `iva.anual.reconciliacion.deducible-303`.
- `iva.anual.resultado-regimen-general` should be reviewed against
  `iva.anual.reconciliacion.resultado-303`.

If the annual totals from your records and the reconciliation values taken from 303 diverge, do not force the 390 to pass first. Review the annual period's records, each 303 calculation, any AEAT receipts, and the values you supplied for the 390. Use the spreadsheet review loop when you need a wider view of the calculation, then run `work calculate` and `work verify` again on the same target. `spreadsheet push` reaches Google, so it is shown as an example that is not run:

```{cli-sequence} modelo-390-sheets-export
```

To review without Google, run `aeat app modelo spreadsheet export` for the
same modelo, year, and period, with the workbook path in `--output`. It writes a local
workbook and refuses to overwrite an existing file unless you add `--replace`.
The spreadsheet workflow is a review surface; it does not submit to AEAT.

## Export and file

The check step in the annual example passed the annual draft as complete (`verificado_completo`). If the check instead reports `cross_period_dependency_unclean` issues that block filing, each named 303 quarter has no recorded filing or AEAT receipt; establish it first (see [What each Modelo 303 quarter needs](#what-each-modelo-303-quarter-needs-before-you-verify)), then check again. The check does not prove that AEAT has accepted the filing. Inspect the saved check report by id when you need the detailed result:

```{cli-sequence} modelo-390-verification-report
```

Export the checked calculation or the one recorded as filed. Export needs the four 303 quarters recorded as filed, so the export and the post-portal steps here are examples that are not run. Export refuses to overwrite an existing file unless you add `--replace`, and refuses when the output folder does not exist. The file carries the development software identity, so keep it for review:

```{cli-sequence} modelo-390-export-file
```

Enter the calculated figures through AEAT's official channel; the full checklist is in [File your modelo at the AEAT portal](file-at-aeat.md). Review the filings you recorded with `filing-record list` and `filing-record view`. `work file` only records the filing in Cadrumo; it does not submit anything to AEAT. The following example lists a profile that recorded nothing, so it reports no records; your own listing has one row per filing you recorded. If the annual return was filed outside Cadrumo, import an external filing record only from an official AEAT receipt. That import needs the official receipt, and reading a stored proof bundle addresses it by id, so both stay examples that are not run:

```{cli-sequence} modelo-390-records-audit
:verify: Confirm the local filing records read back.
```

## What Modelo 390 does not check for you

The tax rules in Cadrumo support Modelo 390's annual 303 reconciliation, but Cadrumo does not enforce every operational policy you might want for a dependable annual filing workflow.

Use these limits when deciding how much to review yourself:

- Modelo 390 does not look at all local filing history regardless of state.
  303-derived resolution is keyed by modelo, filing year, and period.
- Calculation and the check treat 303 filings differently. Calculation fills in
  the values taken from 303 without looking at each quarter's state, so
  `work calculate` can produce a draft. The check is stricter: it blocks until
  each 303 quarter has a recorded filing or an AEAT receipt that was read or
  reconciled (see "What each Modelo 303 quarter needs before you check").
- The annual `work calculate` should not be treated as a general "latest active
  303 calculation" selector. Use `work revision --select filed`,
  `latest-verified`, or exact calculation IDs when you need a specific 303 value.
- Filings you record with `work file`, filed declarations read from AEAT, and
  AEAT receipt reconciliation are related but separate. Cadrumo does not
  require them to agree before every Modelo 390 calculation.
- Missing 303 history can leave the values taken from 303 unavailable or force
  you to supply reviewed values. Calculation can still produce a draft, but the
  check blocks until the missing quarters have a recorded filing or an AEAT
  receipt.
- What AEAT holds does not count unless you explicitly read or reconcile it in
  the workflow you are running.

For a conservative annual close, calculate and review every 303 period, reconcile official AEAT receipts where available, inspect the values taken from 303, and check the annual draft before export. If the command line does not offer the check you need, report that gap instead of documenting it as enforced behavior.

## Next steps

- [Prepare a Modelo 303 VAT filing](modelo-303.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [Reconcile a filed modelo against its AEAT receipt](reconcile.md)
- [The filing workflow](filing-spine.md)
- [Diagnose and repair your local setup](troubleshooting.md)
- [CLI reference](../cli/index.rst)
