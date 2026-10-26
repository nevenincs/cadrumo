# Prepare your first quarterly IRPF filing

This page covers your first quarterly Modelo 130 filing, end to end: bring a
quarter of transactions into your records, classify them as business income and
deductible expenses, prepare the draft, and confirm that it passed the check
before you file it. It is written for a self-employed taxpayer with a NIF or NIE
who is running Cadrumo for the first time.

Cadrumo never submits a return to the Agencia Estatal de Administración Tributaria
(AEAT). It produces the Modelo 130 fichero-BOE file locally; you present that file
through the official AEAT channel.

The commands on this page run live at build time in a fresh, synthetic sandbox.
The transactions, amounts, and taxpayer are invented. Run the same commands
against your own profile to see your own figures.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your
profile](profile-setup.md) walks through it step by step.

## Bring your quarter's transactions in

Import your bank statement for the quarter. This example reads a small
comma-separated statement with two transactions: one payment collected from a
client, and one office-supplies purchase.

```{cli-sequence} import-quarter-transactions
:verify: Confirm both movements are now in the records.
```

The import reads the statement and stores each transaction as an entry in your
records. The listing confirms the two entries landed in the first quarter of 2026.
Point `--provider` at the format your bank exports; list the accepted providers
with:

```{cli-sequence} import-provider-list
:verify: Confirm the import command lists its accepted providers.
```

## Classify each transaction

An imported entry carries a date and an amount, but it does not yet say how the
tax calculation should treat it. Classify each entry before you calculate.

Mark the collected payment as business income and the purchase as a deductible
business expense with a category. Take each transaction id from the listing.
The income classification takes only the business decision.

The expense also needs `--category-id`, the taxable base, the VAT fields, and
`--deduction-kind`, the exact source of the VAT deduction (`domestic_current`
here). Then register the supplier's invoice. The invoice takes its VAT rate as
a percentage (`--iva-rate 21`), while `classify` takes a decimal (`0.21`):

```{cli-sequence} first-quarter-classify-income
:verify: Confirm both rows are classified and the supplier invoice is registered.
```

Link the invoice to the expense row with the `evidence_id` the registration
printed:

```{cli-sequence} first-quarter-link-invoice
```

[Attach invoices and receipts to transactions](ledger-evidence.md) shows the link step with its
output.

List the accepted expense categories any time:

```{cli-sequence} ledger-category-list
:verify: Confirm the accepted expense categories read back.
```

For the full classification workflow (bulk classification, mixed-use shares,
and the review queue), read [Classify transactions](classify-transactions.md).

## Prepare the Modelo 130 draft

Once the quarter's entries are classified, prepare the instalment. The preparation
below sets up a self-employed profile and classified records, then creates the
draft, calculates it, and checks it. Modelo 130 is the IRPF payment on account for
self-employed activity under estimación directa.

```{cli-sequence} modelo-130-first-quarter
:verify: Confirm the draft passed the check before you file it.
```

Read the steps in order:

- Create the draft for Modelo 130, first quarter 2026. The command reports a
  `work_unit_id` that identifies the draft.
- Calculate it. Cadrumo reads your classified records and fills the boxes: box
  `01` is the quarter's income, box `02` the deductible expenses, box `03` the net
  yield, and box `04` the instalment. Box 01 shows 1000.00, not the 1210.00 you
  collected: VAT is never part of your income, so the 210.00 of VAT is left out.
  With the example records the net yield is `500.00` and the instalment is
  `100.00`, twenty percent of the net. The three `--binding ...=0` values are the
  prior-period carries a true first quarter does not have.
- Check the draft. The result reads `granted_verificado_completo` true, so the
  draft is complete and ready to file.

## When your expenses exceed your income

In a quarter where your deductible expenses are larger than your income, the net
yield is negative. The example below records a second office-supplies purchase of
1000.00 in the same quarter, so the expenses reach 1500.00 against 1000.00 of
income, then calculates and checks the draft again:

```{cli-sequence} first-quarter-expenses-exceed-income
:verify: Confirm box 03 is negative and box 19 shows a negative result.
```

What the calculation shows, with the rule each box follows in the official
AEAT instructions for Modelo 130:

- Box `03`, the net yield, is `-500.00`. A negative net yield is entered with a
  minus sign (instructions, box 03).
- Box `04`, the instalment, is `0.00`. The 20 percent applies only to a positive
  net yield; when box 03 is negative, box 04 is zero (instructions, box 04). Box
  `07` is `0.00` too, because this first quarter has no earlier instalments or
  withholdings to subtract.
- Box `13` is the `100.00` reduction for a prior-year net income of 9000 euros or
  less; with no activity last year, that income counts as zero (instructions, box
  13). Box `14` subtracts it from box `12`, which is zero here, and keeps the
  minus sign, so boxes `14`, `17`, and `19` all read `-100.00` (instructions,
  boxes 14, 17, and 19).

Nothing is payable for this quarter: only a positive box 19 is paid (instructions,
section "Ingreso"). In the first, second, or third quarter, a negative box 19 is
declared "A deducir": a later instalment of the same year deducts it through box
15, never by more than that quarter's positive box 14 (instructions, box 15 and
section "A deducir"). In the fourth quarter, a negative result is declared
"Negativa" instead. The calculation also reports the amount as
`saldo-negativo-fin-periodo`, `100.00`, and the draft passes the check like any
other. For how later quarters build on this one, see [Prepare a Modelo 130 IRPF
instalment](modelo-130.md#each-quarter-is-cumulative).

## Check the figures and record the filing

The result of the check is the signal that the draft is ready. The check refuses
until every deductible-expense entry has its purchase invoice linked as a
supporting document, so the classification step registered the supplier invoice
and linked it before you calculate. Keep that order: a draft bundles its
supporting documents when you check it, so an invoice attached afterwards does
not reach the filing.

The sequence below exports the checked draft and then records the filing.
Export refuses to overwrite an existing file unless you add `--replace`;
[The filing workflow](filing-spine.md) explains the export rules.

```{cli-sequence} first-quarter-export-file
:verify: Confirm the export succeeds and the filing record stays local.
```

A later quarter builds on this one: leave the three prior-period values unset
so Cadrumo takes them from your recorded filings. See
[Prepare a Modelo 130 IRPF instalment](modelo-130.md) for the cumulative
year-to-date behaviour.

## Next steps

- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Classify transactions](classify-transactions.md)
- [The filing workflow](filing-spine.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
