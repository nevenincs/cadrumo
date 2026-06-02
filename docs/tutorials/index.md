# Build your first modelo, start to finish

By the end of this tutorial you'll have produced one complete filing: a quarterly IRPF payment-on-account on Modelo 130 (the quarterly instalment for self-employed workers under direct-estimation IRPF), for one example taxpayer, ready to file with AEAT (Agencia Estatal de Administración Tributaria, the Spanish Tax Agency).

You'll carry one worked example the whole way through:

- **Modelo:** 130, the quarterly IRPF payment-on-account.
- **Year:** 2026.
- **Period:** `1T`, the first quarter (January–March).
- **Revision:** `2019-y-siguientes`, the registry revision that covers 2019 and later filings.
- **Taxpayer:** one natural person, the active profile you create in the first step.
- **Transaction file:** the bundled `src/aeat/tests/fixtures/financial/synthetic-transactions.csv`.

The whole flow stays on your machine. The app never submits to AEAT — `file` marks a revision as internally filed and stops there. You do the real filing yourself, outside the app, using the fichero-BOE file (the fixed-width text file AEAT accepts for upload) that `export` writes for you.

The lifecycle runs five verbs in order:

1. `create` — open a work unit for the modelo, year, period, and revision (Step 4).
2. `calculate` — persist a draft calculation, entering the income and expense figures (Step 4).
3. `verify` — check the draft against the verified-complete contract (Step 5).
4. `file` — mark the verified revision as internally filed (Step 5).
5. `aeat app modelo export` — write the local fichero-BOE file (Step 6).

`create` and `calculate` each print a 64-character identifier. Copy each one from its command's output into the next command as you go.

## Prerequisites

Before you build a modelo, you need three things: a working `aeat` command, an active profile, and the bundled transaction file.

### Get the `aeat` command working

Install the `aeat` command by following the bootstrap steps in the [getting-started guide](../getting-started.md): clone the repository, then run `uv sync` from the project root.

You need two things on your machine first:

- **Python 3.13 or newer**
- **The [uv package manager](https://docs.astral.sh/uv/)**

Once `uv sync` finishes, confirm the command works:

```
aeat --version
```

This prints a single line:

```
aeat 0.1.0
```

The CLI has two root command families. Use `aeat config` for setup tasks such as profiles and diagnostics. Use `aeat app` for the tax workflow: ledger, modelo, and registry.

### Create a profile

A profile (your saved taxpayer identity and settings) is required by every workflow command. Create one before you go any further:

```
aeat config profile create NAME
```

Replace `NAME` with a label for the filer. For a non-interactive run, add `--quiet` and `--tax-id`:

```
aeat config profile create tutorial --quiet --tax-id 12345678Z
```

### Find the sample transaction file

The project ships a sample transaction file at:

```
src/aeat/tests/fixtures/financial/synthetic-transactions.csv
```

This tutorial uses that file throughout. To work from a copy, copy it out of the fixtures path before you start.

## Step 1: create the example taxpayer profile

Every profile needs a unique label and a NIF (Número de Identificación Fiscal, the Spanish tax identification number). In this tutorial you'll create one named `tutorial` for an example taxpayer whose NIF is `12345678Z`.

Run the create verb in non-interactive mode so the values land exactly as written:

```
aeat config profile create tutorial --quiet --tax-id 12345678Z
```

On success, the command prints four tab-separated lines:

```
profile	tutorial
status	created
active_profile	tutorial
next	aeat app modelo work create
```

- `profile` echoes the label you chose.
- `status` is `created`, confirming the profile was written.
- `active_profile` repeats `tutorial` — a new profile becomes the active one and later commands act on it.
- `next` points to the verb you'll run in Step 4.

If the command reports that the profile already exists, the label is already taken. Choose a fresh label, or switch to the existing one with `aeat config profile switch tutorial`.

## Step 2: import the example transactions

With your profile ready from Step 1, load the bundled transaction file into its ledger. The ledger is the set of bank transactions the app reads when it builds a modelo.

Run the import verb and pass the fixture path:

```
aeat app ledger import src/aeat/tests/fixtures/financial/synthetic-transactions.csv --provider csv
```

The `--provider csv` option tells the app to read the file as a comma- or semicolon-separated statement. Both flags are required. The command prints a tab-separated summary:

```
Rows	2
Entries imported	2
Skipped	0
```

`Rows` counts the data rows read. `Entries imported` counts the transactions saved. `Skipped` counts duplicates left out.

To see what landed, run the list verb:

```
aeat app ledger list
```

The command prints a header followed by one row per transaction:

```
ACCOUNTING LEDGER TRANSACTIONS
5caeee4b	5caeee4b...	2026-04-10	1234.56	Cobro factura F-2026-020	pending
4b101fb8	4b101fb8...	2026-04-11	-49.99	Pago software trimestral	pending
```

Each row carries a short transaction ID (the prefix), the full ID, the date, the amount, the description, and a review status. Newly imported transactions arrive with status `pending` until you classify them in Step 3.

For the full provider list and global flag options, see the [CLI reference](../cli/index.rst).

## Step 3: classify the transactions

Each row in the ledger now sits unreviewed. In this step you tell the ledger what each transaction is for tax purposes: a wholly-business item, a personal one, or a mixed-use cost split between the two.

Use `aeat app ledger classify` for every transaction in this tutorial. Pass the short transaction ID (copied from the `ledger list` output) and a classification:

```
aeat app ledger classify --id 5caeee4b --classification BUSINESS
```

The command prints a confirmation block:

```
ID	5caeee4b...
Date	2026-04-10
Amount	1234.56
Description	Cobro factura F-2026-020
Review status	reviewed
```

The `Review status` line changes from `pending` to `reviewed` — that is the signal that the row landed.

Classify the expense transaction as `BUSINESS` too:

```
aeat app ledger classify --id 4b101fb8 --classification BUSINESS
```

When every row reads `reviewed`, the ledger is ready for the calculation step.

For full classify and allocate options, including mixed-use splits and category IDs, see the [how-to guide](../how-to/index.md).

## Step 4: work the modelo with `aeat app modelo work`

With an active profile and classified transactions, you're ready to provision a work unit, enter the income and expense figures, and run the calculation. This step uses two verbs: `create` provisions the work unit, and `calculate` enters the data, runs the engine, and prints the casillas (the numbered boxes on the official tax form).

### Find the revision ID

A work unit is keyed on four axes: the modelo, the year, the period, and the registry revision. To confirm the revision ID for Modelo 130, run:

```
aeat app modelo describe 130
```

The output lists the available revision IDs. For 2026, the revision is `2019-y-siguientes`.

### Create the work unit

Provision the work unit with the four axes:

```
aeat app modelo work create --modelo 130 --year 2026 --period 1T --revision 2019-y-siguientes
```

The output reports `created` for a fresh work unit:

```
operation	modelo.work.create
status	created
work_unit_id	<64-character-id>
modelo	130
filing_year	2026
period	1T
revision_id	2019-y-siguientes
state	borrador
```

`borrador` (the Spanish word for draft) is the initial lifecycle state. Copy the `work_unit_id` from this output — you'll pass it to `calculate` next.

### Enter the figures and calculate

Pass the work unit ID, then supply income and expense figures with repeated `--casilla` options in `CASILLA=DECIMAL` form. Casilla 01 holds income; casilla 02 holds deductible expenses:

```
aeat app modelo work calculate <WORK_UNIT_ID> --casilla 01=12000.00 --casilla 02=4000.00
```

Replace `<WORK_UNIT_ID>` with the ID from the `create` output. The command runs the engine, persists a new draft, and prints the result. Each run saves a fresh draft and never overwrites an earlier one.

### Read the result

Look for casilla 07 in the output — the partial result of section I. For income of 12,000 and expenses of 4,000, the engine applies the 20% payment-on-account rate to the net (12,000 − 4,000 = 8,000; 20% = 1,600):

```
casilla	07	1600.00
```

That figure is your evidence the engine ran correctly.

The closing sentence names the calculation revision ID and confirms the save:

```
Saved as draft calculation revision <id> (state: borrador).
```

Copy this calculation revision ID — you'll pass it to `verify` in Step 5.

## Step 5: verify the computed declaration

You now have a calculation revision ID from Step 4. Verification checks the revision against the verified-complete contract: every required casilla resolved, every binding satisfied, and no blocking findings left open.

Run the verify verb with the revision ID you saved in Step 4:

```
aeat app modelo work verify <calculation-revision-id>
```

To record who signed off on the verification, add `--by`:

```
aeat app modelo work verify <calculation-revision-id> --by "Your Name"
```

### Read the verdict

The command emits a verification report. For a clean declaration, the output shows:

```
completeness_status     complete
granted_verificado_completo     true
finding_count   0
```

`granted_verificado_completo: true` is the green light for the export step. The revision advances to the `verificado_completo` lifecycle state.

Once the verdict reads `complete`, mark the revision as internally filed:

```
aeat app modelo work file <calculation-revision-id>
```

The command confirms the filing with `internal only - does not submit to AEAT`. It records the event in your local history; it does not transmit anything.

If the verdict comes back `incomplete` or `blocked`, the report lists each unresolved casilla and each blocking finding. Resolve those items and run `verify` again. For the full verification-report workflow, see the [how-to guide](../how-to/index.md).

## Step 6: export the file you'll file yourself

The verified revision is the only thing `export` accepts — a raw borrador (draft) is refused. This step turns that verified revision into a file you can upload.

Export the work unit using the work unit ID from Step 4:

```
aeat app modelo export <WORK_UNIT_ID> --output borrador.boe
```

Both the work unit ID and `--output` are required. The command writes a local fichero-BOE file and prints a receipt:

```
output_path	borrador.boe
byte_size	<n>
file_sha256	<checksum>
```

Three fields confirm what landed on disk: `output_path` where the file was written, `byte_size` how large it is, and `file_sha256` the checksum. Use `file_sha256` to confirm the file you upload to AEAT is the file the app produced.

The app never submits to AEAT. You upload `borrador.boe` yourself in the AEAT portal.

## What you accomplished

You took one modelo from nothing to a filed revision and an AEAT-compatible file on disk. Along the way you ran five verbs:

- `aeat app modelo work create` opened a work unit for the period.
- `aeat app modelo work calculate` produced the calculated draft revision.
- `aeat app modelo work verify <revision>` granted `verificado_completo`.
- `aeat app modelo work file <revision>` recorded the internal filing.
- `aeat app modelo export <work-unit> --output borrador.boe` wrote the local fichero-BOE file.

Nothing you did here reached AEAT: `work file` records the filing for your own history, `export` writes a local file, and you submit that file to AEAT yourself.

## Where to go next

- To repeat one part of this workflow on its own — recalculating a revision, exporting a fichero-BOE file, or classifying transactions with mixed-use splits — see the [how-to guide](../how-to/index.md).
- To understand why the app stops at a local file and never submits to AEAT, see the [explanation](../explanation/index.md).
- For every command, flag, and exit code, see the [CLI reference](../cli/index.rst).
- If something goes wrong, run `aeat config repair` for a full diagnostic report.
