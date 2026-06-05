# Import and classify a bank statement

Use this guide to turn bank-statement rows into ledger records that a modelo can
calculate from. A ledger is the local record store under your active taxpayer
profile. A modelo is a Spanish tax form.

Everything in this guide is local. `aeat` imports, checks, and updates your local
records. It never contacts the Agencia Estatal de Administración Tributaria
(AEAT) from this workflow.

## Before you start

You need:

- `aeat` installed. If it is not installed, start with
  [Get started with aeat](../getting-started.md).
- An active taxpayer profile. This is the profile that `aeat app` commands read
  and update. If you do not have one, create it with
  [Set up your taxpayer profile](profile-setup.md).
- A bank statement file, or a directory of statement files.

## Preview the import

Run a dry run first. A dry run shows what `aeat` would import and saves no rows:

```
aeat app ledger import ./statement.csv --provider auto --dry-run
```

`--provider auto` asks `aeat` to detect the statement format. If detection picks
the wrong format, replace `auto` with the exact provider. The supported provider
values are listed in the [CLI reference](../cli/index.rst).

## Save the imported rows

When the dry run looks right, repeat the command without `--dry-run`:

```
aeat app ledger import ./statement.csv --provider auto
```

Add `--verify` when you want `aeat` to run import diagnostics for the
statement:

```
aeat app ledger import ./statement.csv --provider auto --verify
```

If those diagnostics should refer to a different original file, pass it with
`--source`:

```
aeat app ledger import ./processed.csv --provider csv --verify --source ./statement.csv
```

## Review imported rows

List the imported rows:

```
aeat app ledger list
```

Use `--filter` to narrow the list by period, classification, issue, import,
direction, or text. For a period, pass `period=<period>`:

```
aeat app ledger list --filter period=2026-03
```

Copy the transaction id from the list, then inspect one row before changing it:

```
aeat app ledger view <transaction-id>
```

A transaction id is the row identifier printed by `aeat app ledger list`. The
`view` command shows the stored fields for that row, including amount,
counterparty, classification, IVA fields, and notes when they exist.

## Classify rows

List the accepted category ids before classifying expenses:

```
aeat app ledger categories
```

A category id is the ledger's name for a tax category. Expense rows normally
need one before a modelo can calculate from them. For income rows, `aeat` uses
the transaction direction, so you do not need `--category-id`.

Mark a fully business-related transaction:

```
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id>
```

Mark a personal transaction:

```
aeat app ledger classify --id <transaction-id> --classification PERSONAL
```

If the row needs tax fields, add only the fields that apply to that transaction:

```
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id> --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
```

For the complete set of classification, IVA, IRPF, and counterparty fields, use
the [CLI reference](../cli/index.rst).

## Record mixed business and personal use

Use allocation when one transaction is partly business-related and partly
personal. The business percentage is a value from `0` to `1`:

```
aeat app ledger allocate --id <transaction-id> --business-pct 0.5 --category-id <category-id>
```

`0` means personal, `1` means fully business, and a value between them means
mixed use. If you already created a usage ratio for this taxpayer profile, add
`--usage-ratio-id`. Use `--prorrata-reference` only for IVA workflows that need
a prorrata reference.

## Check readiness for the period

Run preflight for the filing period before calculating a modelo. Preflight is
the local readiness check for ledger facts:

```
aeat app ledger preflight --period 2026Q1
```

Use the period token that matches the return you plan to calculate, such as
`2026Q1`, `2026-03`, or `2026`.

Preflight reports missing facts such as category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference. Fix the rows it names, then run
preflight again.

Check the overall ledger state for the same period:

```
aeat app ledger status --period 2026Q1
```

Continue only when the period is ready.

## If a command stops with an error

If a command reports that no profile is active, the period is invalid, or the
ledger is not ready, use
[Diagnose and repair your local setup](troubleshooting.md). Use that page to fix
setup and readiness problems.

## Next steps

- [Quickstart: produce a modelo file](quickstart.md)
- [Standard filing workflow](filing-spine.md)
- [CLI reference](../cli/index.rst)
