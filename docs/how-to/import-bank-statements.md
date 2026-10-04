# Import and manage transactions

This page covers the transaction workflow in your records: importing your bank
statement, adding any missing transactions by hand, reviewing and correcting
them, and checking readiness before a calculation. A line on a bank statement
is just a date and an amount - the tax meaning is added later, in
classification.

Your bank records are not added automatically. aeat imports only when you run
an import command. Tax calculations use the transactions you have saved under
the active profile.

## Before you start

You need:

- a working `aeat` command
- an active taxpayer profile; see [Set up your taxpayer profile](profile-setup.md)
- your profile passphrase. The tool prompts for it the first time it opens your
  encrypted storage in a session
- a bank statement file or directory, unless you are adding transactions by hand
- for AEAT census-derived home-office ratios, reviewed censo facts; see
  [Maintain Modelo 036 census facts in your profile](censo-update.md)

Confirm the active profile before you write transaction data:

```{cli-sequence} import-confirm-profile
:verify: Confirm a profile is active before you write transaction data.
```

## Statement file format

`--provider csv` reads bank exports in the BBVA, Santander, CaixaBank, Revolut,
and N26 layouts. `aeat` detects the delimiter and matches the header row to a
layout. The Spanish layouts use comma decimals; Revolut and N26 use period
decimals. The first line is the column header; each later line is one movement.
A BBVA-style file looks like this:

```text
Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda
2026-02-10;2026-02-10;Venta cliente;1.210,00;1.210,00;EUR
2026-02-11;2026-02-11;Compra material;-605,00;605,00;EUR
```

The sign of `Importe` carries the direction: a positive amount is income, a
negative amount is an expense.

## Preview an import

Run a dry run first. A dry run shows what `aeat` would import and saves no rows.
Then repeat the command without `--dry-run` to save the rows. The sequence
previews the standard quarter's statement, imports it, and confirms one imported
row:

```{cli-sequence} import-preview-save
:verify: Confirm the statement's rows were imported into the records.
```

`--provider csv` names the statement format. `--provider auto` asks `aeat` to
detect it. The recognized providers are `auto`, `csv`, `ofx`, `qfx`, `xlsx`,
`xls`, and `pdf-n26` (an N26 PDF statement). If detection picks the wrong format,
replace `auto` with the exact provider - run `aeat app ledger import --help` or
see the [CLI reference](../cli/index.rst) for the current provider list.

If the path does not exist or is not readable, the command refuses cleanly and
names the path (`Invalid value for '--file': the path ... does not exist or is
not a readable file.`); fix the path and run it again.

## Save imported rows with diagnostics

Add `--verify` when you want import diagnostics alongside the save:

```{cli-sequence} import-diagnostics
:verify: Confirm the checked import saved the statement's rows.
```

If the diagnostics should check the rows against a different original file,
pass it with `--verify-source <original>`. Use `--period` with `--year` only when
you intentionally want to label the import with a filing period; leave both out
and `aeat` assigns the period from each transaction's date automatically.

## Add one transaction manually

Use `ledger add` when a transaction is missing from imported statements.
Required fields are date, amount, direction, and description. Write the amount
as a positive figure - the direction carries whether money came in or went out,
and the command refuses a negative amount. `OUTGOING` is for expenses;
`INCOMING` is for income:

```{cli-sequence} import-add-manual
:verify: Confirm a manually added transaction is stored with its direction.
```

The third direction, `INTERNAL_TRANSFER`, records money moved between your own
accounts.

### Record tax details on a manual transaction

`ledger add` accepts the same tax fields you set during classification, so you
record a complete transaction in one step. `--amount` is the gross total
(taxable base plus VAT), and the tool refuses the row if the base plus VAT does
not match the gross to the cent:

```{cli-sequence} import-add-tax-details
:verify: Confirm the tax fields were recorded on the manual transaction.
```

Useful optional fields:

- `--currency` records a non-euro amount; it defaults to `EUR`.
- `--counterparty` records who you paid or were paid by.
- `--category-id` assigns the income or expense category. Run
  `aeat app ledger categories` to list the ids.
- `--taxable-base`, `--iva-rate`, and `--iva-amount` record the VAT breakdown.
- `--deduction-kind` names the source of a purchase's input VAT deduction, and
  `--purchase-invoice-evidence-id` links the invoice's supporting document. Without a
  deduction kind the input VAT is not deducted. See
  {ref}`Classify transactions <say-where-the-input-iva-comes-from>`.
- `--irpf-category` records the IRPF (personal income tax) category.
- `--source-jurisdiction` records the country a movement belongs to, as an
  ISO two-letter code, which matters for non-resident scopes.
- `--notes` adds a short note.

For a part-business, part-personal movement, set `--classification MIXED` and the
business share with `--business-pct`, a value from `0` to `1`. For the VAT
category, EU member-state, and usage-ratio semantics behind these fields, see
[Classify transactions](classify-transactions.md).

Use the invoice commands when you also need to track whether an invoice exists
separately from the bank transaction. Received invoices are supplier invoices you
owe; issued invoices are customer invoices owed to you. `invoice add` takes the
VAT rate as a percentage, such as `--iva-rate 21`, unlike `ledger add`, which
takes a decimal:

```{cli-sequence} import-invoice-records
:verify: Confirm the recorded invoice resolved to a payable invoice.
```

For the full invoice-record workflow, see
[Attach invoices and receipts to transactions](ledger-evidence.md).

## Review rows

List rows, narrow the list with filters, inspect one row, and read its event
history. The example starts from the imported quarter and walks the read
commands:

```{cli-sequence} import-review-rows
:verify: Confirm the inspected row reads the imported income movement.
```

For a broader review queue, use `ledger review` to inspect selected rows and
`ledger check` to report anomalies across all your records and periods. Both are
local-only:

```{cli-sequence} import-review-check
:verify: Confirm the aggregate records check runs cleanly.
```

## Export rows for review

Export your records to a file. The `--year` and `--period` filter keeps the
export aligned with the transaction dates. Exports are review snapshots, not an
edit-and-reimport path:

```{cli-sequence} import-export-rows
:verify: Confirm the records export for the requested period.
```

Add `--export-format xlsx` to write an XLSX snapshot instead, and use the annual
period code `0A` when a whole year is the review scope.

To change saved rows, use `ledger update`, `ledger classify`, `ledger allocate`,
`ledger split`, or `ledger merge`.

## Update a row

Use `ledger update` for editable transaction fields - date, value date, amount,
direction, currency, counterparty, description, taxable base, VAT rate, VAT
amount, IRPF category, notes, or group label:

```{cli-sequence} import-update-row
:verify: Confirm the row's description and VAT fields were updated.
```

An update gives the transaction a new id; an id you wrote down earlier still
resolves in `view`, `history`, and `track`. For the full correction workflow -
splitting, merging, archiving, stashing, removing, and resetting rows - see
[Correct mistakes in your records](correct-ledger-entries.md).

(attach-evidence-to-a-transaction)=
## Attach a supporting document to a transaction

Attach a secure supporting document for a purchase to a transaction. The
supporting document's id comes from `aeat app ledger evidence add`, which
registers the invoice PDF or image as an encrypted supporting document. The
example registers the invoice PDF as a supporting document, records the
expense, then attaches one to the other. `evidence add` takes the VAT rate
as a percentage (`21`), while `ledger add` takes a decimal (`0.21`):

```{cli-sequence} import-attach-evidence
:verify: Confirm the purchase invoice attached to the transaction.
```

`attach` is the single door for a purchase's supporting documents. The `link`
command links a transaction to an invoice record only. Its `--invoice-id` option takes the id
that `aeat app ledger invoice add` prints, or the id of an imported or
reconciled invoice. See
[Attach invoices and receipts to transactions](ledger-evidence.md) for the full
workflow for supporting documents and invoice records, including the `--attachment-id` option and its current
limitation.

Pull a document straight from Google Drive into encrypted storage with `evidence pull`. This command reaches Google Drive, so it runs against your own
authorized account rather than in the documentation sandbox:

```{cli-sequence} import-evidence-pull
```

The command downloads the Drive file, stores its bytes encrypted with the
transaction, and keeps the original link as a record of where the file came
from. Gmail links, arbitrary URLs, and Drive files outside the granted scope are
refused - a supporting document always carries the document itself, never a
bare link. For a refused source, download
the document yourself, register it with `aeat app ledger evidence add`, and
attach it with `aeat app ledger attach --purchase-invoice-evidence-id`.

## Fix a wrong row

Splitting a mixed movement into parts, merging a wrong split back, and
archiving, stashing, removing, or resetting rows are all corrections.
[Correct mistakes in your records](correct-ledger-entries.md) owns that
workflow, with an example for each command and guidance on picking the
least destructive fix.

## Classify rows

Classify rows before calculation. At a minimum, imported business rows need
a business/personal/mixed decision, and expense rows need a category:

```{cli-sequence} import-classify-rows
:verify: Confirm the imported expense is classified as business.
```

[Classify transactions](classify-transactions.md) owns the full workflow -
bulk CSV classification, mixed-use allocation, tax fields, stored rules,
and [LLM-assisted suggestions](classify-with-llm.md).

## Check readiness for a filing period

Run preflight before calculating a modelo, then check the overall state of your records.
Preflight looks at each record inside the period and flags anything still missing
before any sums are trusted - a missing classification, category, base, VAT
amount, VAT rate, split reference, or unconvertible currency:

```{cli-sequence} import-check-readiness
:verify: Confirm the period's readiness is reported for the classified quarter.
```

The check changes nothing; it names the rows that are not ready so you fix the
raw material before trusting any total. Continue to calculation only when the
active profile and target period are ready enough for the modelo you are
preparing.

For calculation review in Google Sheets, see
[Review calculations with Google Sheets](review-with-google-sheets.md). That
workflow exports a modelo calculation to Sheets; it is separate from the CSV/XLSX export of your records.

## If a command stops with an error

If a command reports that no profile is active, the period is invalid, or your records are not ready, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Import, export, and supporting documents](../reference/import-export-and-evidence.md) -
  understand what imported rows mean and how they differ from tax facts and
  proof of filing.
- [Classify transactions](classify-transactions.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [How your records become tax figures](../explanation/from-records-to-figures.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [Quickstart: prepare a modelo filing](quickstart.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
