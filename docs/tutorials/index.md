# Build your first Modelo 130 filing

This tutorial guides you through creating a quarterly personal income tax
payment-on-account (Modelo 130) for an example taxpayer. You'll export a local
fichero-BOE file, a text file that follows the official Boletín Oficial del
Estado (BOE) format, at the end.

`aeat` prepares local files for Spanish tax forms. It does not submit them to
the Agencia Estatal de Administración Tributaria (AEAT). You upload the exported
file yourself through the AEAT portal.

The ledger is the local record of the transactions you import. The filing target
is the modelo, year, and period you prepare.

## Prerequisites

You need:

* A working `aeat` command. If you need to install it, start with
  [Quickstart: produce a modelo file](../how-to/quickstart.md).
* A taxpayer profile. For every profile setup flag and question, see
  [Set up your taxpayer profile](../how-to/profile-setup.md).
* The sample transaction file included with this tutorial.

## Step 1: Create your taxpayer profile

Run:

```bash
aeat config profile create tutorial --quiet --accept-defaults --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez"
```

The sample `--tax-id` has the same shape as a Spanish citizen's NIF (their DNI
number). Use your own NIF, CIF, DNI, or NIE when you create a real profile.

The command output should identify `tutorial` as the active profile and point to
the next modelo work command. It looks similar to:

```
profile	tutorial
status	created
active_profile	tutorial
next	aeat app modelo work create
```

## Step 2: Import your transactions

First, create a text file named `transactions.csv` in your working directory and paste the following content into it:

```csv
Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda
10/04/2026;10/04/2026;Cobro factura F-2026-020;1234,56;5234,56;EUR
11/04/2026;11/04/2026;Pago software trimestral;-49,99;5184,57;EUR
```

Then load these sample transactions into the local ledger:

```bash
aeat app ledger import transactions.csv --provider csv
```

To verify the import, run:

```bash
aeat app ledger list
```

Your output should include transaction rows like these:

```
ACCOUNTING LEDGER TRANSACTIONS
5caeee4b	5caeee4b...	2026-04-10	1234.56	Cobro factura F-2026-020	pending
4b101fb8	4b101fb8...	2026-04-11	-49.99	Pago software trimestral	pending
```

## Step 3: Classify your transactions

Find the transaction IDs in the first column of the output from `aeat app ledger list`. In this example, they are `5caeee4b` and `4b101fb8`. Note that if you run this with different data, your IDs will be different.

Classify these transactions as business activity (replace `5caeee4b` and `4b101fb8` with the actual IDs from your list output):

```bash
aeat app ledger classify --id 5caeee4b --classification BUSINESS
aeat app ledger classify --id 4b101fb8 --classification BUSINESS
```

To confirm the review status changed to `reviewed`, run:

```bash
aeat app ledger list
```

## Step 4: Create a new draft

Create the Modelo 130 draft for the first quarter of 2026:

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 1T
```

The command returns the visible filing target:

```
modelo	130
filing_year	2026
period	1T
revision_id	2019-y-siguientes
state	borrador
```

`aeat` chooses the rule set for that modelo, year, and period, so you do not
need to choose one.

## Step 5: Calculate your tax figures

Calculate the draft by repeating the same visible filing target:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T
```

The command saves the draft for the same filing target. If calculation or
verification reports a missing manual value, prior-period value, or binding,
pause the tutorial and use
[Review and supply calculation inputs](../how-to/review-calculation-values.md)
to inspect the modelo casillas and decide the correct value.

## Step 6: Verify your draft

Verify the current calculation for the same filing:

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
```

Confirm the output shows that the status is complete and that verification is
granted:

```
completeness_status     complete
granted_verificado_completo     true
finding_count   0
```

## Step 7: Export the file for AEAT

Generate the fichero-BOE file:

```bash
aeat app modelo export --modelo 130 --year 2026 --period 1T --output borrador.boe
```

Observe the output path and checksum. The checksum is a file fingerprint you can
use to check the file later.

## Step 8: Upload to the AEAT portal and record the filing locally

Once you have your `borrador.boe` file, you need to file it with the tax agency:
1. Log in to the official [Agencia Tributaria Sede Electrónica](https://sede.agenciatributaria.gob.es/).
2. Navigate to the Modelo 130 presentation page.
3. Select the option to submit or present by file upload (*fichero*).
4. Click **Importar** (Import) and upload your `borrador.boe` file. The form boxes (*casillas*) will be automatically filled with your calculated figures.
5. Review and sign the presentation, and download the receipt PDF (*justificante*).

The detailed handoff checklist is in
[Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

After completing the upload in the AEAT portal, record a local filing marker in `aeat` to mark this verified draft as filed:

```bash
aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

This command saves a local marker only. It does not submit anything to AEAT.

## What you completed

You completed the local setup and filing workflow for Modelo 130 without copying
raw internal IDs between commands. The command output may still print work-unit
and calculation-revision IDs for audit, replay, and advanced exact addressing,
but the normal workflow uses the visible filing target: modelo, year, and
period.

## Next steps and help

For task-focused procedures, read the [how-to guides](../how-to/index.md). To
understand the advanced filing workspace and revision model, read
[How filings, work units, and calculation revisions fit together](../how-to/filing-spine.md).
For the underlying concepts, read [How calculations work](../explanation/ledger-to-calculation.md).
For manual casilla values, offsets, and binding mechanics, read
[Review and supply calculation inputs](../how-to/review-calculation-values.md).

If a command stops or the local state looks wrong, use
[Diagnose and repair your local setup](../how-to/troubleshooting.md).

