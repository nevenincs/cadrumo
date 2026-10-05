(prepare-a-modelo-303-iva-filing)=
# Prepare a Modelo 303 VAT filing

Use this guide when the active profile must prepare Modelo 303. Modelo 303 is
the Spanish VAT (value-added tax) self-assessment (`autoliquidación`) used here
to calculate standard quarterly VAT filings. Monthly VAT-liquidation profiles,
such as those in the Registro de Devolución Mensual (REDEME) or large-company
taxpayers, use monthly Modelo 303 periods. Voluntary enrolment in the
Suministro Inmediato de Información (SII) alone remains quarterly. Its official title is "Modelo 303.
Impuesto sobre el Valor Añadido. Autoliquidación."

Cadrumo does not submit Modelo 303 to the Agencia Estatal de Administración
Tributaria (AEAT). `export` writes the filing layout, but its envelope header
carries Cadrumo's all-zero development software identity because the product
holds no AEAT software-developer registration, so AEAT will not accept the
file. Read the calculated box values back and enter them through the official
AEAT channel yourself.

The tool needs your passphrase and prompts for it.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your
profile](profile-setup.md) walks through it step by step.

## The complete first-quarter chain

This is the full path from classified records with supporting documents to a
quarter recorded as filed, for a first-period filer. The example starts from a
self-employed profile with classified first-quarter records: one sale and one
purchase, with the supplier's purchase invoice attached as an encrypted
supporting document. It then creates the draft, calculates it, checks it,
records the filing in Cadrumo, and exports. The details that make the example
work follow it.

The Modelo 303 export writes a review file whose envelope carries the all-zero
development software identity. Enter the calculated box values at the AEAT
portal, as [File your modelo at the AEAT portal](file-at-aeat.md) describes.

```{cli-sequence} modelo-303-first-quarter
:verify: Confirm the draft passes the check, records the filing in Cadrumo, and exports with the development identity.
```

Load-bearing details for building this state yourself:

- Create the profile with `--quiet` for the non-interactive form. A bare
  `aeat config profile create me` opens an interactive wizard. The profile MUST
  carry `--name` and `--surnames`, or filing later refuses with `requires the
  operator name`.
- `--activity-start-date 2026-01-01` tells Cadrumo that no earlier period is
  needed for a first period. Without it, the check blocks on the previous quarter.
- `ledger add --amount` is the GROSS amount (`--taxable-base` + `--iva-amount`).
  Here `1000 + 210 = 1210` and `500 + 105 = 605`. The tool enforces that the
  taxable base plus VAT equals the gross to the cent.
- A deductible-expense entry needs `--category-id`. List the valid ids with `aeat
  app ledger categories`. The example uses `material_oficina`.
- Modelo 303 makes you state whether the return is a joint self-assessment
  (autoliquidación conjunta). The example passes `--no-joint-return-elected`
  for no. Cadrumo never assumes the answer, and `work calculate` refuses
  without one of `--joint-return-elected` or `--no-joint-return-elected`.
- Calculation charges 210.00 of VAT on the sale (`IVA repercutido`) and deducts
  105.00 on the purchase (`IVA soportado`), so box 71 (Resultado final) is 105.00,
  the VAT due for the quarter. The deductible VAT counts at calculate time; the
  attached supporting document is what lets the entry be filed, not what changes
  the figure.
- Attach the purchase invoice as a supporting document *before* you check. The
  check finalizes the calculation and saves a snapshot of the entries it used, so
  the supporting document must already be on the expense entry. A locked entry
  cannot take a late attachment.
- `verify` reports `completeness complete` and `granted true`, and `work file`
  records the filing in Cadrumo. `export` writes the file with the all-zero
  development software identity and says so in a warning notice.
- Box 65 ("% atribuible a la Administración del Estado") resolves to 100
  automatically for a común-territory profile, so box 66 and the headline box 71
  (Resultado final) carry the full régimen-general result. Cadrumo supports
  común-territory profiles only.

The rest of this guide explains each step and the checks around it.

## Before you create the draft

Start with the pieces that decide whether Modelo 303 applies and which data can
be calculated:

- [Set up your taxpayer profile](profile-setup.md) and check the active
  profile. Modelo 303 depends on VAT facts such as `--iva-regime`,
  `--iva-sii-enrolled`, `--iva-redeme-enrolled`, ROI/OSS enrollment, activity
  and residence facts, and the active profile.
- Check your census facts before calculating - see
  [Maintain Modelo 036 census facts in your profile](censo-update.md). Censo
  facts can affect profile readiness and local classifications.
- [Plan your filing calendar](filing-calendar.md) and confirm the period code
  with {ref}`Period codes and dates <period-tokens-and-dates>`.
  Standard non-exempt
  profiles use quarterly periods such as `1T`; monthly VAT-liquidation profiles
  such as REDEME or large-company taxpayers use monthly periods such as `01`.
- [Import or add your transactions](import-bank-statements.md), then [classify
  them](classify-transactions.md). Modelo 303 needs enough VAT detail on business
  entries to route amounts from your records to the right VAT boxes.
- If calculation reports missing inputs, use
  [Review and supply calculation inputs](review-calculation-values.md) before
  forcing manual values into the filing.

## What Modelo 303 calculates

Modelo 303 calculates a period VAT self-assessment: VAT charged to customers minus
deductible VAT paid, plus declared adjustments and prior-period compensation, to
produce the result, payment, refund, and carry-forward boxes for the period.

In ordinary cases based on your records, calculation can combine:

- VAT charged to customers (`IVA repercutido`) from classified income and sales
  entries.
- Deductible VAT paid on purchases and expenses (`IVA soportado`) from classified
  supplier entries.
- VAT categories, rates, directions, taxable bases, VAT amounts, business
  percentage, currency/FX support, and intracommunity/reverse-charge treatment
  recorded on your entries.
- Profile facts, including VAT regime and profile-derived values that Cadrumo
  fills into the form.
- Prior Modelo 303 VAT compensation state, when the target period needs pending
  compensation from the previous period.
- Values you enter yourself, only where the tax rules or command help say a
  value cannot be derived from the profile, your records, constants, or saved
  history.

Do not read that list as "every Modelo 303 box comes from your records." Many
boxes remain manual, taken from the profile, set by the tax rules, or sourced
from prior filing history rather than transaction entries.

Classification matters because the calculation does not guess whether an entry is
business, personal, mixed-use, deductible, domestic, exempt, intracommunity, or
reverse-charge. Entries that are unclassified or missing required VAT fields can
block calculation or leave values missing.

When you add an entry by hand, pass the GROSS amount on `--amount` and the VAT
detail explicitly with `aeat app ledger add`.

`--amount` is `--taxable-base` plus `--iva-amount`, and the tool refuses the entry
if they do not match to the cent. A deductible-expense entry also needs a
`--category-id`; list the valid ids with `aeat app ledger categories`.

(create-the-work-unit)=
## Create the declaration

Create or reuse the saved declaration for the active profile, modelo, filing
year, period, and version of the official form. This needs an active profile;
create one first if you have none with `aeat config profile create`, then open
the declaration with `aeat app modelo work create`. The complete chain runs
`work create`.

Running the command again for the same target gives the same result. If a
declaration already exists for the active profile, Modelo 303, year, period, and
version of the official form, Cadrumo returns it instead of creating a duplicate.

Use the same target on the later commands, for example `aeat app modelo work
status`.

For routine work, the target (`--modelo`, `--year`, `--period`) is all you need.
Reference-number workflows are covered in [The filing workflow](filing-spine.md).

(check-the-ledger-period)=
## Check the period's records

The period you pass to the declaration controls which of your records
calculation uses. Calculation selects the entries for the requested modelo,
year, and period through the tax rules and period conversion. The records and
modelo commands share one grammar: pass the AEAT period code with `--year`. For
example, `--year 2026 --period 1T` is the first quarter; monthly code `01`
with `--year 2026` is January.

Check that period before calculating:

```{cli-sequence} modelo-303-ledger-period
:verify: Confirm the quarter's records read back ready to calculate.
```

The period uses the transaction's operation date: `raw.value_date` when
available, otherwise `raw.booked_date`. The entry must also be in an active
lifecycle state and carry enough classification, direction, business
percentage, VAT category/rate/amount, and currency/FX information for the rule
that fills the box that needs it.

Calculation also checks your records for tax readiness for versions of the
official form that total VAT from your records. The preflight can catch missing
VAT facts, unclassified entries, non-declarable categories, unsupported
currencies, and similar issues before a draft is trusted. Regimen simplificado
is treated differently: those profiles provide the simplificado boxes manually
instead of passing the ordinary VAT preflight on your records.

Cadrumo does not silently choose a quarter from today's date. The declaration's
`--year` and `--period` are the target.

## Calculate the draft

Run calculation for the same target with `aeat app modelo work calculate`. The
complete chain runs this. Modelo 303 always needs `--joint-return-elected` or
`--no-joint-return-elected`. In the last period of the year (`4T` or `12`) it
also needs the Modelo 390 confirmation flags - see
[Prepare the annual Modelo 390 VAT summary](modelo-390.md).

Calculation picks the version of the official form for that declaration, reads
the active profile's records for the target period, takes values from the
profile and from earlier filings through the tax rules, runs the formulas of the
tax rules, and saves a draft calculation. At this point your records for the
period are not frozen. The draft stores the calculated box values, typed
observations with their sources, snapshots of the rules and inputs it used, and
the contributing `source_transaction_ids`.

Re-running calculation does not edit the previous calculation; it saves a new
one, or reuses an identical one, and makes it the declaration's current
calculation.

If the command reports missing values or missing boxes, inspect them before adding
values:

```{cli-sequence} modelo-303-inspect-boxes
:verify: Confirm the draft's missing values and the modelo's required boxes read back.
```

Only provide `--binding`, `--casilla`, `--relation`, or Modelo 303-specific flags
when the command help or the inspection output identifies the value you are
supplying. For example, inspect the VAT compensation wallet before relying on a
prior compensation amount:

```{cli-sequence} modelo-303-wallet
:verify: Confirm the VAT compensation wallet seeds and reads back its balance.
```

Use `--amount 0` only for a true first Modelo 303 period with no previous
pending VAT compensation.

## Review the calculated values

List the saved calculations, then show the current calculation's saved values:

```{cli-sequence} modelo-303-revision
:verify: Confirm the saved calculations and the current calculation's values read back.
```

The view of a saved calculation shows its id and state, the saved box values,
typed observations where available, formula ids, operands, legal and source
references, source transaction ids, and, after the check, the snapshot of your
records and the supporting-document fields.

For a local calculation report, run `aeat app modelo work report --output FILE`
on a checked declaration or one recorded as filed; it writes CSV by default and
is not an official AEAT document. For a spreadsheet review loop, see
[Review calculations with Google Sheets](review-with-google-sheets.md). For
manual inputs, values Cadrumo fills in, offsets, and choosing among earlier
calculations, see
[Review and supply calculation inputs](review-calculation-values.md).

(verify-and-file)=
## Check and record the filing

Check the selected calculation with `aeat app modelo work verify`. The
complete chain runs the check and records the filing end to end.

The check tests the selected draft for completeness. The report shows the
calculation id, completeness status, whether the check was granted or blocked,
resolved and missing boxes, issues with legal and source references where
available, and the next action.

When the check passes, Cadrumo saves a snapshot of the entries and supporting
documents behind the draft's `source_transaction_ids` with that calculation.
The snapshot lets later checks detect whether a contributing entry changed or
disappeared, which would make the calculation out of date. It does not lock your
records as a whole, and it does not freeze unrelated entries.

`aeat app modelo export` stamps Modelo 303's envelope with Cadrumo's all-zero
development software identity (program `0000`, developer NIF `00000000T`),
reports `software_identity_grade` as `development_mock`, and warns with
`modelo.export.development_software_identity`. That identity is a
product-release fact, not taxpayer or presenter data, so the command never
takes it from the active profile. AEAT does not accept a file carrying it.

Export refuses to overwrite an existing file unless you add `--replace`, and
refuses when the output folder does not exist. `--payment-election` (`ingreso`
or `domiciliacion`) and `--refund-election` (`compensar` or `devolver`) choose
how a positive or negative result is settled. The defaults are `ingreso` and
`compensar`. `cuenta_corriente` is not supported yet and is refused. `devolver`
is accepted only in a period where a refund is allowed (the last period of the
year, or any period for a REDEME profile) and needs a refund account on the
profile.

Read the checked figures back with `aeat app modelo work revision` and enter
them at the AEAT portal. The check, recording the filing, and the snapshot
described above all still apply.

If you want Cadrumo to record that the checked calculation was filed, after you
submit through AEAT, record the filing with `aeat app modelo work file`.
`work file` only records the filing in Cadrumo; it is not an AEAT submission.

## Periods, carry-forward, and special cases

Modelo 303 supports quarterly and monthly period codes. The profile determines
which cadence appears in the filing calendar: ordinary non-exempt profiles are
quarterly, while monthly VAT-liquidation profiles such as REDEME or large-company
taxpayers are monthly. Voluntary SII enrolment by itself does not switch Modelo
303 from quarterly to monthly.

The source-backed behavior is:

- A target is always profile + modelo + year + period, with the version of the
  official form chosen from that target unless you pass an exact version.
- The records used are bounded by the declaration's period, not by a rolling
  automatic slice.
- Prior VAT compensation is taken from earlier Modelo 303 filings or from the
  compensation history you seeded, not guessed from your current records.
- The check and recording the filing can carry a snapshot of the contributing
  entries and their supporting documents; the check output does not print the
  full contents of your records, but what is needed as proof is preserved in the
  snapshot.

Invalid or unsupported period codes are rejected, and `4T` is distinct from
annual periods such as `0A`. Cadrumo does not cross-check Modelo 303 periods
for an operation declared twice. It relies on date windows, source transaction
ids, import duplicate diagnostics, and the guards on finalized calculations, so
check for double counting yourself when you move entries between periods.

If you are trying to handle an ambiguous period, a rollover between periods, or
possible double accounting, do not invent a workaround in the Modelo 303 guide.
Use exact declaration or calculation IDs, inspect the saved calculations, and see
[Troubleshooting](troubleshooting.md). If the command line does not offer the
check you need, report the gap instead of changing your records to make the filing
pass.

## Next steps

- [The filing workflow](filing-spine.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Plan your filing calendar](filing-calendar.md)
- [Reconcile a filed modelo against its AEAT receipt](reconcile.md)
- [Diagnose and repair your local setup](troubleshooting.md)
