# Build your first Spanish tax filing: Modelo 130 Tutorial

This tutorial guides you through creating a quarterly IRPF payment-on-account (Modelo 130) for an example taxpayer and exporting a local BOE file.
The application helps you prepare your tax figures locally.
It doesn't submit them directly to the Spanish Tax Agency (AEAT).
You'll upload the exported file yourself to the AEAT portal.
If you need definitions for terms like `fichero-BOE`, `ledger`, and `casilla`, refer to the [central glossary](../glossary.md).

## Prerequisites

You need the following items before starting:
* A working `aeat` command. If you need to install the command, follow the [installation guide](../getting-started.md).
* Access to your transaction files.

## Step 1: Create your taxpayer profile

To manage your tax data, you must create a profile.
Run the command `aeat config profile create tutorial --quiet --tax-id 12345678Z --name "Ana" --surnames "García López"`.
Verify the command output matches this text:

```
profile	tutorial
status	created
active_profile	tutorial
next	aeat app modelo work create
```

## Step 2: Import your transactions

You must load your transaction records into the application ledger.
Run this command to import the transactions:

```bash
aeat app ledger import src/aeat/tests/fixtures/financial/synthetic-transactions.csv --provider csv
```

To verify the import, run `aeat app ledger list`.
Confirm your output matches the following:

```
ACCOUNTING LEDGER TRANSACTIONS
5caeee4b	5caeee4b...	2026-04-10	1234.56	Cobro factura F-2026-020	pending
4b101fb8	4b101fb8...	2026-04-11	-49.99	Pago software trimestral	pending
```

## Step 3: Classify your transactions

To categorize your income and expenses, you need to assign classifications.
Run these commands to classify the imported transactions as `BUSINESS`:

1. `aeat app ledger classify --id 5caeee4b --classification BUSINESS`
2. `aeat app ledger classify --id 4b101fb8 --classification BUSINESS`

To confirm the review status changes to `reviewed`, run `aeat app ledger list`.

## Step 4: Provision your tax form

To create a work unit, run:

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 1T
```

The rules revision automatically resolves to `2019-y-siguientes`. The command may print internal IDs for audit and support, but you do not need them for the next command:

```
operation	modelo.work.create
status	created
modelo	130
filing_year	2026
period	1T
revision_id	2019-y-siguientes
state	borrador
```

## Step 5: Calculate your tax figures

To compute the draft calculation, run:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --casilla 01=12000.00 --casilla 02=4000.00 --binding irpf.previous_year_economic_activity_net_income=0
```

Use the `--binding` flag to supply the net income from the previous year. You need this flag because this fact isn't in the ledger of the current quarter. The command saves the result as the current draft calculation for Modelo 130, year 2026, period `1T`.

## Step 6: Verify your draft

To check the draft, run:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
```

By default, `verify` selects the current draft for that modelo, year, and period. Confirm the output shows that the status is complete and that the system grants verification:

```
completeness_status     complete
granted_verificado_completo     true
finding_count   0
```

## Step 7: Mark the return as filed

To mark the revision as internally filed, run:

```bash
aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

By default, `file` selects the current verified revision for that modelo, year, and period. Confirm the command reports that the system saved the local marker.

## Step 8: Export the file for AEAT

To generate the fichero-BOE file, run:

```bash
aeat app modelo export --modelo 130 --year 2026 --period 1T --output borrador.boe
```

By default, `export` uses the filed revision when one exists, otherwise the current verified revision. Observe the SHA-256 checksum in the output.

## Summary of your journey

You completed the setup and filing process for Modelo 130. Throughout this tutorial, you accomplished the following:

- Installed the application.
- Created your profile.
- Imported and classified your financial data.
- Managed the filing status using the lifecycle verbs without copying internal IDs between commands.

## Next steps and help

To look up specific concepts for everyday use, read the [how-to guides](../how-to/index.md) and [explanation](../explanation/index.md).

If you find a bug or need help, report the issue on the [project issue tracker](https://github.com/wgergely/aeat/issues).
