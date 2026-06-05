# Work with transaction data

Use this guide when your ledger is not ready yet. It covers importing bank
statements, adding transactions by hand, reviewing rows, editing or removing
rows, and handing the ledger to classification and calculation.

The ledger is local to the active taxpayer profile. `aeat` does not
automatically sync your bank. It imports only when you run an import command,
and calculation consumes the saved ledger rows that belong to the active
profile.

## Before you start

You need:

- a working `aeat` command
- an active taxpayer profile; see [Set up your taxpayer profile](profile-setup.md)
- a bank statement file or directory, unless you are adding transactions by hand

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

`--provider auto` asks `aeat` to detect the statement format. Current provider
values shown by command help include `auto`, `csv`, `ofx`, `qfx`, `xlsx`,
`excel`, `n26`, `pdf`, and `pdf-n26`.

If detection picks the wrong format, replace `auto` with the exact provider.

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

Use `--period` only when you intentionally want to tag the import with a fiscal
period.

## Add a transaction manually

Use `ledger add` when a transaction is missing from imported statements:

```bash
aeat app ledger add --date 2026-03-15 --amount -49.99 --direction OUTGOING --description "Software subscription"
```

Required fields are date, signed amount, direction, and description. Optional
fields include value date, currency, counterparty, classification, business
percentage, category id, taxable base, IVA rate, IVA amount, IRPF category,
notes, and source jurisdiction.

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

## Update a row

Use `ledger update` for editable transaction fields:

```bash
aeat app ledger update --id <transaction-id> --description "Corrected description"
aeat app ledger update --id <transaction-id> --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
```

Use this for corrections such as date, value date, amount, direction, currency,
counterparty, description, taxable base, IVA rate, IVA amount, IRPF category,
notes, or group label.

## Remove, archive, or stash a row

Use the least destructive action that matches the problem:

- `archive` when a row should stay in local history but no longer be part of
  ordinary work.
- `stash` when a row should be set aside for later review.
- `remove` when the row should be deleted from the active ledger.

Examples:

```bash
aeat app ledger archive --id <transaction-id> --reason "duplicate imported row" --yes
aeat app ledger stash --id <transaction-id> --reason "waiting for invoice" --yes
aeat app ledger remove --id <transaction-id> --reason "wrong file imported" --dry-run
aeat app ledger remove --id <transaction-id> --reason "wrong file imported" --yes
```

`remove --dry-run` reports effects without deleting the row. `archive`,
`stash`, and confirmed `remove` are local ledger changes; they do not contact
AEAT.

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

## Check readiness for a filing period

Run preflight before calculating a modelo:

```bash
aeat app ledger preflight --period 2026Q1
```

Preflight reports missing facts such as category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference. Fix the rows it names, then run
preflight again.

Check the overall ledger state:

```bash
aeat app ledger status --period 2026Q1
```

Continue to calculation only when the active profile and target period are
ready enough for the modelo you are preparing.

## If a command stops with an error

If a command reports that no profile is active, the period is invalid, or the
ledger is not ready, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Classify transactions](classify-transactions.md)
- [Quickstart: produce a modelo file](quickstart.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
