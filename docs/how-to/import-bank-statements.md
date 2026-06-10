# Work with Transactions

Use this guide to bring your bank movements into aeat so they can feed your
tax calculations. Import your bank statement, add any missing transactions by
hand, review and correct them, then hand them to classification before running
a calculation.

Your bank records are not added automatically. aeat imports only when you run
an import command. Tax calculations use the transactions you have saved under
the active profile.

## Before you start

You need:

- a working `aeat` command
- an active taxpayer profile; see [Set up your taxpayer profile](profile-setup.md)
- a bank statement file or directory, unless you are adding transactions by hand
- for AEAT census-derived home-office ratios, reviewed censo facts; see
  [Link Modelo 036 census information](censo-update.md)

Confirm the active profile before you write transaction data:

```bash
aeat config profile status
```

## Preview an import

Run a dry run first. A dry run shows what `aeat` would import and saves no
rows:

```bash
aeat app ledger import ./statement.csv --provider auto --dry-run
```

`--provider auto` asks `aeat` to detect the statement format. If detection
picks the wrong format, replace `auto` with the exact provider - run
`aeat app ledger import --help` or see the [CLI reference](../cli/index.rst)
for the current provider list.

## Save imported rows

When the dry run looks right, repeat the command without `--dry-run`:

```bash
aeat app ledger import ./statement.csv --provider auto
```

Add `--verify` when you want import diagnostics:

```bash
aeat app ledger import ./statement.csv --provider auto --verify
```

If the diagnostic source should point at a different original file, pass it
with `--source`:

```bash
aeat app ledger import ./processed.csv --provider csv --verify --source ./statement.csv
```

Use `--period` only when you intentionally want to label the import with a
fiscal period. Leave it out — aeat assigns the period from each transaction's
date automatically.

## Add one transaction manually

Use `ledger add` when a transaction is missing from imported statements:

```bash
aeat app ledger add --date 2026-03-15 --amount=-49.99 --direction OUTGOING --description "Software subscription"
```

Required fields are date, amount (`-` prefix for expenses, no prefix for
income), direction, and description. `OUTGOING` is for expenses — money
you paid out. `INCOMING` is for income — money you received.

For a received payment or issued invoice, use `INCOMING`:

```bash
aeat app ledger add --date 2026-03-20 --amount 121.00 --direction INCOMING --description "Client payment"
```

For an expense or supplier invoice, use `OUTGOING`:

```bash
aeat app ledger add --date 2026-03-21 --amount=-60.50 --direction OUTGOING --description "Office supplies"
```

Use the invoice commands when you also need to track whether an invoice exists
separately from the bank movement:

```bash
aeat app ledger payable-invoice --help
aeat app ledger collectible-invoice --help
```

Payable invoices are supplier invoices you owe. Collectible invoices are
customer invoices owed to you.

## Review rows

List rows:

```bash
aeat app ledger list
```

Narrow the list with filters:

```bash
aeat app ledger list --filter period=2026-03
aeat app ledger list --filter classification=NOT_YET_PROCESSED
aeat app ledger list --limit 20 --offset 20
```

Inspect one row before changing it:

```bash
aeat app ledger view <transaction-id>
```

See the event history for one row:

```bash
aeat app ledger history <transaction-id>
aeat app ledger track <transaction-id>
```

For a broader review queue, use:

```bash
aeat app ledger review --filter period=2026-1T
aeat app ledger check
```

`review` helps inspect selected ledger rows. `check` reports aggregate ledger
anomalies across periods and is local-only.

## Export rows for review

Export the active ledger to a file:

```bash
aeat app ledger export --output ./ledger-2026-q1.csv --year 2026 --period 1T
```

The `--year` and `--period` filter keeps the export aligned with the tutorial
transaction dates. A transaction dated `2026-03-15` belongs in `--year 2026
--period 1T`, so it appears in the command above. Use the annual token `0A`
when a whole year is the review scope:

```bash
aeat app ledger export --output ./ledger-2026.xlsx --export-format xlsx --year 2026 --period 0A
```

Exports are review snapshots. They are not a general edit-and-reimport
mutation path for existing ledger rows. To change saved rows, use `ledger
update`, `ledger classify`, `ledger allocate`, `ledger split`, or `ledger
merge`.

## Update a row

Use `ledger update` for editable transaction fields:

```bash
aeat app ledger update --id <transaction-id> --description "Corrected description"
aeat app ledger update --id <transaction-id> --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
```

Use this for corrections such as date, value date, amount, direction, currency,
counterparty, description, taxable base, IVA rate, IVA amount, IRPF category,
notes, or group label.

Add or modify notes when you need a short operator explanation:

```bash
aeat app ledger update --id <transaction-id> --notes "Receipt checked against supplier PDF"
```

Attach secure purchase evidence, link an invoice, or bind a stored attachment id:

```bash
# Attach purchase evidence or other attachment files to a transaction
aeat app ledger attach --id <transaction-id> --purchase-invoice-evidence-id <evidence-id>
aeat app ledger attach --id <transaction-id> --attachment-id <attachment-id>

# Link a transaction bidirectionally with an invoice and/or purchase evidence in one command
aeat app ledger link --id <transaction-id> --invoice-id <invoice-id> --evidence-id <evidence-id>
```

Record a link to a Gmail, Google Drive, or URL without copying the file:

```bash
aeat app ledger doclink --id <transaction-id> --source GOOGLE_DRIVE --reference <drive-file-id> --note "Supplier invoice"
```

The link is saved with the transaction. aeat does not access or download the
file.

## Split and re-join a transaction

Use `split` when one bank movement contains parts that need different
categories or business percentages. For example, split a `-121.00` movement
into software and personal parts:

```bash
aeat app ledger split --id <transaction-id> --child-amount=-100.00 --child-description "Software business part" --child-amount=-21.00 --child-description "Personal part" --reason "mixed receipt" --yes
```

aeat replaces the original transaction with two separate entries — one for
each part. Classify each one separately:

```bash
aeat app ledger classify --id <business-child-id> --classification BUSINESS --category-id <category-id>
aeat app ledger classify --id <personal-child-id> --classification PERSONAL
```

If the split was wrong, merge the complete child cohort:

```bash
aeat app ledger merge --child-id <business-child-id> --child-id <personal-child-id> --reason "undo split" --yes
```

You must include all the parts you split — aeat will not let you re-merge only
some of them.

## Remove, archive, stash, or reset ledger rows

For the full correction workflow — updating fields, removing, splitting,
merging, and reviewing history — see
[Correct mistakes in your ledger](correct-ledger-entries.md). For attaching
invoices and receipts, see
[Attach invoices and receipts](ledger-evidence.md).

Use the least destructive action that matches the problem:

- `archive` — keep the transaction in your history but exclude it from ordinary
  work. Use this when a movement was imported by mistake but you want to keep a
  record of it.
- `stash` — set aside a transaction you are not sure about. A stashed
  transaction leaves the everyday lists. Both stash and archive are
  reversible: `restore` returns the transaction to active.
- `restore` — return a stashed or archived transaction to active.
- `remove` — delete the transaction from your active records.
- `reset` — clear the entire transaction list for the active profile and start
  over. **Use with care — this removes all imported data.**

Examples:

```bash
aeat app ledger archive --id <transaction-id> --reason "duplicate imported row" --yes
aeat app ledger stash --id <transaction-id> --reason "waiting for invoice" --yes
aeat app ledger restore --id <transaction-id> --reason "stashed by mistake" --yes
aeat app ledger remove --id <transaction-id> --reason "wrong file imported" --yes
aeat app ledger reset --reason "re-importing all statements" --yes
```

`remove --dry-run` and `reset --dry-run` report the effects without modifying the storage. These commands are entirely local ledger changes and never contact the AEAT.

## Classify rows

Classify rows before calculation. At a minimum, imported business rows usually
need a business/personal/mixed classification, and expense rows normally need a
category.

Start with:

```bash
aeat app ledger categories
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id>
```

Use [Classify transactions](classify-transactions.md) for the full
classification workflow, including bulk CSV classification, mixed-use
allocation, tax fields, and LLM-assisted suggestions.

For repeated descriptions, stored rules can classify matching unclassified
transactions automatically:

```bash
aeat app ledger rule add --description-pattern "software" --classification BUSINESS --category-id <category-id>
aeat app ledger rule apply --dry-run
aeat app ledger rule apply
```

For model-assisted suggestions, use
[Classify transactions with an LLM](classify-with-llm.md). That
page explains provider setup, what row data is sent to the local provider, what
is previewed, what is applied, and how to override the result.

## Batch edit classifications

Use batch classification when many reviewed rows need the same kind of
classification update. The implemented batch path is `ledger classify
--from-csv`; it accepts `transaction_id`, `classification`, and optional
`category_id`.

1. Filter and export the rows you want to review:

   ```bash
   aeat app ledger list --filter period=2026-1T --filter classification=NOT_YET_PROCESSED
   aeat app ledger export --output ./ledger-2026-q1-review.csv --year 2026 --period 1T
   ```

2. Build a small classification CSV from the reviewed transaction ids:

   ```text
   transaction_id,classification,category_id
   <expense-id>,BUSINESS,<category-id>
   <personal-id>,PERSONAL,
   ```

3. Apply it:

   ```bash
   aeat app ledger classify --from-csv ./classifications.csv
   ```

4. Review afterwards:

   ```bash
   aeat app ledger list --filter period=2026-1T
   aeat app ledger preflight --year 2026 --period 1T
   ```

This batch path does not bulk edit descriptions, amounts, IVA fields, notes, or
attachments. Edit those one row at a time with `ledger update`, `ledger attach`,
or `ledger doclink`.

## Check readiness for a filing period

Run preflight before calculating a modelo:

```bash
aeat app ledger preflight --year 2026 --period 1T
```

Preflight reports missing facts such as category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference. Fix the rows it names, then run
preflight again.

Check the overall ledger state:

```bash
aeat app ledger status --year 2026 --period 1T
```

Continue to calculation only when the active profile and target period are
ready enough for the modelo you are preparing.

For calculation review in Google Sheets, see
[Review calculations with Google Sheets](review-with-google-sheets.md). That
workflow exports a modelo calculation surface to Sheets; it is separate from
ledger CSV/XLSX export.

## If a command stops with an error

If a command reports that no profile is active, the period is invalid, or the
ledger is not ready, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Classify transactions](classify-transactions.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [How calculations work](../explanation/ledger-to-calculation.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)

