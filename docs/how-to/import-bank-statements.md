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
@step Confirm the active profile.
@result aeat --format json config profile status
@expect result.active_profile == "docs-sequence-sandbox"
@expect exit_code == 0
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
@step Preview the import - a dry run saves no rows.
aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv --dry-run
@step Save the rows by repeating the command without --dry-run.
aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Confirm an imported row is now in the ledger.
@result aeat --format json app ledger view 71a5db2b
@expect result.transaction.description == "Cobro factura F-2026-001 servicios de consultoria"
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
@step Import the statement with diagnostics.
aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv --verify
@step Confirm the imported row is present.
@result aeat --format json app ledger view 71a5db2b
@expect result.transaction.direction == "INCOMING"
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
@step Record an expense you paid out.
aeat --format json app ledger add --date 2026-03-15 --amount 49.99 --direction OUTGOING --description "Software subscription" --idempotency-key import-add-software
@capture transaction_id result.transaction_id
@step Record a payment you received.
aeat --format json app ledger add --date 2026-03-20 --amount 121.00 --direction INCOMING --description "Client payment" --idempotency-key import-add-client
@step Record a supplier expense.
aeat --format json app ledger add --date 2026-03-21 --amount 60.50 --direction OUTGOING --description "Office supplies" --idempotency-key import-add-supplies
@step Confirm the first transaction was stored as an outgoing expense.
@result aeat --format json app ledger view {transaction_id}
@expect result.transaction.amount == "49.99"
@expect result.transaction.direction == "OUTGOING"
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
@step Record a purchase with its full IVA breakdown in one step.
aeat --format json app ledger add --date 2026-03-21 --amount 121.00 --direction OUTGOING --description "Office supplies" --counterparty "Papeleria SL" --category-id material_oficina --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00 --notes "Receipt filed" --idempotency-key import-tax-details
@capture transaction_id result.transaction_id
@step Confirm the taxable base and IVA were stored.
@result aeat --format json app ledger view {transaction_id}
@expect result.transaction.taxable_base == "100"
@expect result.transaction.iva_amount == "21"
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
@step Record a supplier's received invoice.
aeat --format json app ledger invoice add --kind received --counterparty-nif B12345678 --invoice-number "2026-0142" --invoice-date 2026-03-21
@capture invoice_id result.invoice_id
@step List issued invoices.
aeat app ledger invoice list --kind issued
@step Confirm the received invoice is a payable invoice.
@result aeat --format json app ledger invoice view {invoice_id} --kind received
@expect result.source_kind == "payable_invoice"
```

For the full invoice-record workflow, see
[Attach invoices and receipts](ledger-evidence.md).

## Review rows

List rows, narrow the list with filters, inspect one row, and read its event
history. The sequence imports the quarter and walks the read commands:

```{cli-sequence} import-review-rows
:verify: Confirm the inspected row reads the imported income movement.
@step Import the quarter's movements so there are rows to review.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step List every row.
aeat app ledger list
@step Narrow the list with filters.
aeat app ledger list --filter period=1T --filter year=2026
@step List only the rows still needing a decision.
aeat app ledger list --filter classification=NOT_YET_PROCESSED
@step Inspect one row before changing it.
aeat app ledger view 71a5db2b
@step Read the event history for the row.
aeat app ledger history 71a5db2b
@step Track the same row.
aeat app ledger track 71a5db2b
@step Confirm the row is the imported income movement.
@result aeat --format json app ledger view 71a5db2b
@expect result.transaction.direction == "INCOMING"
```

For a broader review queue, use `ledger review` to inspect selected rows and
`ledger check` to report aggregate ledger anomalies across periods. Both are
local-only:

```{cli-sequence} import-review-check
:verify: Confirm the aggregate ledger check runs cleanly.
@step Import the quarter's movements so there is something to review.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Inspect selected ledger rows for a period.
aeat app ledger review --filter period=1T --filter year=2026
@step Report aggregate ledger anomalies across periods.
@result aeat --format json app ledger check
@expect result.ready == false
@expect exit_code == 0
```

## Export rows for review

Export the active ledger to a file. The `--year` and `--period` filter keeps the
export aligned with the transaction dates. Exports are review snapshots, not an
edit-and-reimport path:

```{cli-sequence} import-export-rows
:verify: Confirm the ledger exports for the requested period.
@step Import the quarter's movements so there is something to export.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Export the first quarter to a CSV snapshot.
@result aeat --format json app ledger export --output ./ledger-2026-q1.csv --year 2026 --period 1T
@expect result.export_format == "csv"
@expect exit_code == 0
@step Write an XLSX snapshot of the whole year instead. XLSX embeds a per-run id, so it is shown as a display frame.
@static aeat app ledger export --output ./ledger-2026.xlsx --export-format xlsx --year 2026 --period 0A
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
@step Record a transaction to update.
@setup aeat --format json app ledger add --date 2026-03-21 --amount 121.00 --direction OUTGOING --description "Office supplies" --idempotency-key import-update
@capture transaction_id result.transaction_id
@step Correct the description, capturing the new id the update rotates to.
aeat --format json app ledger update {transaction_id} --description "Corrected description"
@capture after_description result.transaction_id
@step Record the IVA breakdown against the current id.
aeat --format json app ledger update {after_description} --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
@capture after_iva result.transaction_id
@step Add an operator note against the current id.
aeat app ledger update {after_iva} --notes "Receipt checked against supplier PDF"
@step The original id still resolves for reads; confirm the correction landed.
@result aeat --format json app ledger view {transaction_id}
@expect result.transaction.taxable_base == "100"
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
@step Record the purchase invoice as encrypted evidence.
@setup aeat --format json app ledger evidence add fixtures/factura-material-oficina.pdf --supplier "Papeleria SL" --invoice-number "2026-0142" --invoice-date 2026-03-21 --taxable-base 100.00 --iva-rate 21 --iva-amount 21.00
@capture evidence_id result.evidence_id
@step Record the expense the invoice supports.
@setup aeat --format json app ledger add --date 2026-03-21 --amount 121.00 --direction OUTGOING --description "Office supplies" --category-id material_oficina --taxable-base 100 --iva-rate 0.21 --iva-amount 21 --idempotency-key import-attach
@capture transaction_id result.transaction_id
@step Attach the purchase evidence to the transaction.
aeat app ledger attach {transaction_id} --purchase-invoice-evidence-id {evidence_id}
@step Confirm the transaction resolves after the attachment.
@result aeat --format json app ledger view {transaction_id}
@expect result.transaction.purchase_invoice_evidence_id == "6509f06abb0c5756"
@expect exit_code == 0
```

The same purchase-evidence link is also available through the `link` command,
addressing the transaction and evidence by id:

```{cli-sequence} import-link-evidence
@step Link purchase evidence to a transaction by id, an alternative to attach.
@static aeat app ledger link <transaction-id> --evidence-id <evidence-id>
```

The `link --invoice-id` option expects an id from the reconciliation invoice
catalogue (populated by the import and reconcile flows), not an id from `aeat app
ledger invoice add`. See
[Attach invoices and receipts](ledger-evidence.md) for the full evidence and
invoice-record workflow, including the `--attachment-id` option and its current
limitation.

Pull a document straight from Google Drive into encrypted evidence storage with
`doclink`. This command reaches Google Drive, so it runs against your own
authorized account rather than in the documentation sandbox:

```{cli-sequence} import-doclink
@step Pull a document from Google Drive into encrypted evidence.
@static aeat app ledger doclink <transaction-id> --source GOOGLE_DRIVE --reference <drive-file-id> --note "Supplier invoice"
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
@step Import the quarter's movements so there is a row to classify.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step List the recognized expense categories.
aeat app ledger categories
@step Classify the imported expense as a business cost with a category.
aeat app ledger classify e3eeac5e --classification BUSINESS --category-id material_oficina
@step Confirm the row now reads business with its category.
@result aeat --format json app ledger view e3eeac5e
@expect result.transaction.business_classification == "BUSINESS"
@expect result.transaction.category_id == "material_oficina"
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
@step Import and classify the quarter's rows.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@setup aeat app ledger classify 71a5db2b --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
@setup aeat app ledger classify e3eeac5e --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105
@step Check the period is ready to calculate.
aeat app ledger preflight --year 2026 --period 1T
@step Read the overall ledger state for the period.
@result aeat --format json app ledger status --year 2026 --period 1T
@expect result.business_income_total == "1210"
@expect exit_code == 0
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
