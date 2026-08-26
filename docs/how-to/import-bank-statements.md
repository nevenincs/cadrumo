# Import and manage transactions

This page covers the ledger's transaction workflow: importing your bank
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
- a master-key passphrase. The tool prompts for it the first time it opens your
  encrypted storage in a session
- a bank statement file or directory, unless you are adding transactions by hand
- for AEAT census-derived home-office ratios, reviewed censo facts; see
  [Link Modelo 036 census information](censo-update.md)

Confirm the active profile before you write transaction data:

```{cli-sequence} import-confirm-profile
:verify: Confirm a profile is active before you write transaction data.
```

## Statement file format

A bank CSV uses a semicolon (`;`) separator and comma decimals. The first
line is the column header; each later line is one movement:

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
:verify: Confirm the statement's rows were imported into the ledger.
```

`--provider csv` names the statement format. `--provider auto` asks `aeat` to
detect it. The recognized providers are `auto`, `csv`, `ofx`, `qfx`, `xlsx`,
`excel`, `n26`, `pdf`, and `pdf-n26`. If detection picks the wrong format,
replace `auto` with the exact provider - run `aeat app ledger import --help` or
see the [CLI reference](../cli/index.rst) for the current provider list.

If the path does not exist, the command refuses cleanly and names the missing
file (`El archivo de origen no existe: ...`); fix the path and run it again.

## Save imported rows with diagnostics

Add `--verify` when you want import diagnostics alongside the save:

```{cli-sequence} import-diagnostics
:verify: Confirm the verified import saved the statement's rows.
```

If the diagnostic source should point at a different original file, pass it with
`--file <original>`. Use `--period` only when you intentionally want to label the
import with a fiscal period; leave it out and aeat assigns the period from each
transaction's date automatically.

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
(taxable base plus IVA), and the tool refuses the row if the base plus IVA does
not match the gross to the cent:

```{cli-sequence} import-add-tax-details
:verify: Confirm the tax fields were recorded on the manual transaction.
```

Useful optional fields:

- `--currency` records a non-euro amount; it defaults to `EUR`.
- `--counterparty` records who you paid or were paid by.
- `--category-id` assigns the income or expense category. Run
  `aeat app ledger categories` to list the ids.
- `--taxable-base`, `--iva-rate`, and `--iva-amount` record the IVA breakdown.
- `--irpf-category` records the IRPF (personal income tax) category.
- `--source-jurisdiction` records the country a movement belongs to, as an
  ISO two-letter code, which matters for non-resident scopes.
- `--notes` adds a short operator note.

For a part-business, part-personal movement, set `--classification MIXED` and the
business share with `--business-pct`, a value from `0` to `1`. For the IVA
category, EU member-state, and usage-ratio semantics behind these fields, see
[Classify transactions](classify-transactions.md).

Use the invoice commands when you also need to track whether an invoice exists
separately from the bank movement. Received invoices are supplier invoices you
owe; issued invoices are customer invoices owed to you:

```{cli-sequence} import-invoice-records
:verify: Confirm the recorded invoice resolved to a payable invoice.
```

For the full invoice-record workflow, see
[Attach invoices and receipts](ledger-evidence.md).

## Review rows

List rows, narrow the list with filters, inspect one row, and read its event
history. The sequence imports the quarter and walks the read commands:

```{cli-sequence} import-review-rows
:verify: Confirm the inspected row reads the imported income movement.
```

For a broader review queue, use `ledger review` to inspect selected rows and
`ledger check` to report aggregate ledger anomalies across periods. Both are
local-only:

```{cli-sequence} import-review-check
:verify: Confirm the aggregate ledger check runs cleanly.
```

## Export rows for review

Export the active ledger to a file. The `--year` and `--period` filter keeps the
export aligned with the transaction dates. Exports are review snapshots, not an
edit-and-reimport path:

```{cli-sequence} import-export-rows
:verify: Confirm the ledger exports for the requested period.
```

Add `--export-format xlsx` to write an XLSX snapshot instead, and use the annual
token `0A` when a whole year is the review scope.

To change saved rows, use `ledger update`, `ledger classify`, `ledger allocate`,
`ledger split`, or `ledger merge`.

## Update a row

Use `ledger update` for editable transaction fields - date, value date, amount,
direction, currency, counterparty, description, taxable base, IVA rate, IVA
amount, IRPF category, notes, or group label:

```{cli-sequence} import-update-row
:verify: Confirm the row's description and IVA fields were updated.
```

An update gives the transaction a new id; an id you wrote down earlier still
resolves in `view`, `history`, and `track`. For the full correction workflow -
splitting, merging, archiving, stashing, removing, and resetting rows - see
[Correct mistakes in your ledger](correct-ledger-entries.md).

## Attach evidence to a transaction

Attach secure purchase evidence to a transaction. The evidence id comes from
`aeat app ledger evidence add`. The sequence records evidence and an expense,
then attaches one to the other:

```{cli-sequence} import-attach-evidence
:verify: Confirm the purchase-invoice evidence attached to the transaction.
```

`attach` is the single door for purchase evidence. The `link` command binds a
transaction to a reconciliation-catalogue invoice only.

The `link --invoice-id` option expects an id from the reconciliation invoice
catalogue (populated by the import and reconcile flows), not an id from `aeat app
ledger invoice add`. See
[Attach invoices and receipts](ledger-evidence.md) for the full evidence and
invoice-record workflow, including the `--attachment-id` option and its current
limitation.

Pull a document straight from Google Drive into encrypted evidence storage with
`evidence pull`. This command reaches Google Drive, so it runs against your own
authorized account rather than in the documentation sandbox:

```{cli-sequence} import-evidence-pull
```

The command downloads the Drive file, stores its bytes encrypted with the
transaction, and keeps the original link as provenance. Gmail links, arbitrary
URLs, and Drive files outside the granted scope are refused - evidence always
carries the document itself, never a bare link. For a refused source, download
the document yourself and attach it with `aeat app ledger attach
--attachment-id`.

## Fix a wrong row

Splitting a mixed movement into parts, merging a wrong split back, and
archiving, stashing, removing, or resetting rows are all corrections.
[Correct mistakes in your ledger](correct-ledger-entries.md) owns that
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

Run preflight before calculating a modelo, then check the overall ledger state.
Preflight looks at each record inside the period and flags anything still missing
before any sums are trusted - a missing classification, category, base, IVA
amount, IVA rate, split reference, or unconvertible currency:

```{cli-sequence} import-check-readiness
:verify: Confirm the period's readiness is reported for the classified quarter.
```

The check changes nothing; it names the rows that are not ready so you fix the
raw material before trusting any total. Continue to calculation only when the
active profile and target period are ready enough for the modelo you are
preparing.

For calculation review in Google Sheets, see
[Review calculations with Google Sheets](review-with-google-sheets.md). That
workflow exports a modelo calculation surface to Sheets; it is separate from
ledger CSV/XLSX export.

## If a command stops with an error

If a command reports that no profile is active, the period is invalid, or the
ledger is not ready, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  understand what imported rows mean and how they differ from tax facts and
  filing evidence.
- [Classify transactions](classify-transactions.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [How your records become tax figures](../explanation/from-records-to-figures.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
