# Build your first modelo, start to finish

New to terms like modelo, casilla, borrador, or IVA? See the [Explanation](../explanation/index.md) and [Reference](../cli/index.rst) before you start.

By the end of this tutorial you'll have produced one complete filing: a quarterly IVA (Impuesto sobre el Valor Añadido) self-assessment on Modelo 303, for one example taxpayer, ready to file with AEAT.

You'll carry one worked example the whole way through:

- **Modelo:** 303, the quarterly IVA self-assessment.
- **Year:** 2026.
- **Period:** `1T`, the first quarter.
- **Revision:** `2023-y-siguientes`, the registry revision that covers 2023 and later filings.
- **Taxpayer:** one natural person, the active profile you create in the first step.

The path is a five-verb lifecycle under `aeat app modelo work`, followed by one export. You'll run them in order:

1. `create` - open a work unit for the example modelo, year, period, and revision.
2. `calculate` - persist a draft (`borrador`) calculation, drawing the IVA figures from your ledger.
3. `verify` - check the draft against the verified-complete contract.
4. `file` - mark the verified revision as internally filed.
5. `aeat app modelo export` - write a local, AEAT-compatible fichero-BOE file.

The whole flow stays on your machine. The app never submits to AEAT. The `file` verb marks a revision as internally filed and stops there - it does not transmit anything. You do the real filing yourself, outside the app, using the fichero that `export` writes for you.

One practical note before you start: `create` and `calculate` each return a 64-character identifier - a `work_unit_id` and a `calculation_revision_id`. You'll copy each one from a command's output into the next command, so keep them to hand as you go.

## Prerequisites

Before you build a modelo, you need three things: a working `aeat` command, an active profile, and a transaction file to import.

### Get the `aeat` command working

The `aeat` command ships with the project. Install it by following the bootstrap steps in the [getting-started guide](../getting-started.md): clone the repository, then run `uv sync` from the project root.

You need two things on your machine first:

- **Python 3.13 or newer**
- **The [uv package manager](https://docs.astral.sh/uv/)**

These are the only hard requirements.

Once `uv sync` finishes, confirm the command works:

```
aeat --version
```

This prints a single line:

```
aeat 0.1.0
```

To see the two command families, run:

```
aeat --help
```

The CLI has exactly two root families. Use `aeat config` for setup tasks such as profiles, AEAT authentication, and diagnostics. Use `aeat app` for the tax workflow over your active profile: ledger, modelo, and registry. The help text renders in Spanish by default, but the command words shown throughout this tutorial (`aeat config profile create`, `aeat app ledger import`) stay the same in every language.

### Create a profile

A profile holds the data for one filer. Every workflow command - importing transactions, building a modelo, exporting a file - runs against an active profile and refuses to run without one. Create one before you go any further:

```
aeat config profile create NAME
```

Replace `NAME` with a label for the filer. The command walks you through setup interactively. For a non-interactive run, add `--quiet` or `--accept-defaults`.

If you skip this step, profile-scoped commands stop with localized guidance telling you to create a profile first.

### Find the sample transaction file

The project ships a small sample transaction file you can import without preparing your own data. It lives in the test fixtures tree:

```
src/aeat/tests/fixtures/financial/synthetic-transactions.csv
```

This file is the cleanest starting point: two transaction rows, UTF-8 encoding, and a standard Spanish-format header with no bank-specific quirks. The same directory holds bank-specific samples (`bbva-sample.csv`, `caixabank-sample.csv`, `santander-sample.csv`, and `revolut-sample.csv`), but stick with `synthetic-transactions.csv` for your first run.

There's no top-level `samples/` folder. To work from a copy, copy the file out of the fixtures path explicitly.

### What you need, at a glance

**Required:**

- A working `aeat` command (verified with `aeat --version`)
- An active profile (`aeat config profile create NAME`)
- A transaction file to import (use the bundled `synthetic-transactions.csv`)

**Optional - not needed for this tutorial:**

- **AEAT authentication** (`aeat config auth`). The build, calculate, verify, and export workflow runs entirely on your machine and never contacts AEAT. Authentication matters only for the live-read diagnostics surface, which this tutorial doesn't use.

One thing `aeat` never does: file to AEAT for you. It builds, checks, and exports a file that you upload yourself. There is no submit command. The project is pre-alpha, so expect breaking changes between versions.

## Step 1: create the example taxpayer profile

Every profile needs a unique label and a tax identifier. In this tutorial you'll create one named `tutorial` for an example taxpayer whose NIF is `12345678Z`.

Run the create verb in non-interactive mode so the values land exactly as written:

```
aeat config profile create tutorial --quiet --tax-id 12345678Z
```

The `--quiet` flag runs the command without prompts, using only the flags you supply. Under `--quiet`, the only required flag is `--tax-id`, which carries the NIF or NIE for the profile. Omit it and the command stops before saving and names `--tax-id` as the missing value.

On success, the command prints four tab-separated lines:

```
profile	tutorial
status	created
active_profile	tutorial
next	aeat app modelo work create
```

Read each line:

- `profile` echoes the label you chose, `tutorial`.
- `status` is the literal token `created`, confirming the profile was written.
- `active_profile` repeats `tutorial` because a new profile becomes the active one. Later commands in this tutorial act on the active profile.
- `next` points to the verb you'll run in Step 2, `aeat app modelo work create`.

If the command reports that the profile already exists, the label is already taken by a live profile. The match ignores case. Choose a fresh label, or switch to the existing one with `aeat config profile switch tutorial`.

## Step 2: import the example transactions

With your profile ready from Step 1, you can load transactions into its ledger. The ledger is the set of bank transactions the app reads when it builds a modelo. In this step you import a small example statement, then list what landed.

### Prepare a sample statement

The importer reads a bank-statement file. The shipped examples use the common Spanish bank export shape:

- Semicolon-delimited columns.
- A header naming the date, description, and amount columns, for example `Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda`.
- A comma as the decimal separator, for example `800,00`.

Save your example file somewhere you can reach from the command line, and note its path. The rest of this step refers to it as `example.csv`.

### Import the file

Run the import verb. Pass the path to your file and the `--provider` option:

```
aeat app ledger import example.csv --provider csv
```

The `--provider` option tells the app how to read the file, and it's required. For a comma- or semicolon-separated statement, use `csv`. To let the app detect the shape, use `auto`. The recognized providers are `auto`, `csv`, `ofx`, `qfx`, `xlsx`, `excel`, `n26`, `pdf`, and `pdf-n26`. If you omit `--provider`, the command stops and reports the missing option. If you pass a value the app doesn't recognize, it lists every accepted provider so you can pick the right one.

The command prints a tab-separated summary of what it loaded:

```
Rows	2
Entries imported	2
Skipped	0
```

`Rows` counts the data rows the app read. `Entries imported` counts the transactions it saved. `Skipped` counts rows it left out, such as duplicates of transactions already in the ledger.

To preview the load without saving anything, add `--dry-run`:

```
aeat app ledger import example.csv --provider csv --dry-run
```

A dry run reports the same counts plus a `DRY RUN MODE` line and a `Notice` line confirming nothing was saved. Use it to check that the app reads your file as you expect before you commit the transactions.

### List the imported transactions

To see what's in the ledger, run the list verb:

```
aeat app ledger list
```

The command reads the active profile's ledger and prints a header followed by one tab-separated row per transaction:

```
ACCOUNTING LEDGER TRANSACTIONS
d73db011	d73db011...f3b79	2024-01-20	800	Concierto Café Mercantil Granada	reviewed
```

Each row carries a short transaction ID, the full ID, the date, the amount, the description, and a review status. The short ID is a unique prefix you can use to refer to a single transaction later. Newly imported transactions arrive with the review status `pending` until you classify them in a later step.

`aeat app ledger list` shows every transaction in the active ledger, with no period filter. For period-scoped or filing-readiness views, use the separate `aeat app ledger status` and `aeat app ledger check` verbs.

### A note on language and output format

The app's default language in this environment is Spanish, so the labels appear in Spanish unless you ask for another language. To see English labels, add the `--language` flag before the `app` group:

```
aeat --language en app ledger import example.csv --provider csv
```

To get machine-readable output instead of text, add `--format json`, also before the `app` group:

```
aeat --format json app ledger list
```

The JSON output wraps the result in a small envelope with the command name and a `result` object. For a listing, `result` holds the bucket ID and a `rows` array, where each row carries the full typed transaction fields. Both verbs run entirely on your machine and never contact AEAT.

The `--language` and `--format` global flags shown here work the same way for every command in this tutorial: place them before the `app` group. Later steps reuse them without repeating the full explanation.

## Step 3: classify and allocate the transactions

You imported the quarter's transactions in Step 2. Each row now sits in the active profile's ledger bucket, unreviewed. In this step you tell the ledger what each transaction is for tax purposes: a wholly-business expense, a personal one, or a mixed-use cost split between the two. Two verbs do this work, both under the `app ledger` group:

- `aeat app ledger classify` records a single outcome - `BUSINESS`, `PERSONAL`, or `MIXED` - for one transaction.
- `aeat app ledger allocate` records a business/private split as a fraction, then derives the classification from that fraction.

Both verbs run locally against the active profile. Neither contacts AEAT.

### A note on the quarter

Classify and allocate take no `--period` or quarter flag. Each transaction carries its own date, and the modelo calculation later selects which transactions fall into the quarter. So "allocate the transactions to the quarter" means: classify the dated rows that belong to that quarter now, and the quarter binding follows from the dates downstream. You're labelling rows, not setting a period.

### Identify a transaction

Both verbs identify a transaction with `--id`. Pass either the full SHA-256 identifier or an unambiguous prefix of it. The full identifier is long, so a prefix is friendlier. Copy an identifier (or a leading slice of one) from the listing you produced in Step 2.

If the prefix matches more than one transaction, the command stops and lists the candidate identifiers so you can disambiguate. Add a few more characters and run it again.

### Classify a wholly-business expense

Take an office-supplies expense that belongs entirely to the business. Classify it as `BUSINESS`:

```
aeat app ledger classify --id <transaction-prefix> --classification BUSINESS
```

The command prints a confirmation block, five tab-separated lines:

```
ID	<sha256>
Date	2025-03-14
Amount	120.00
Description	Office supplies
Review status	reviewed
```

The **Review status** line is the signal that the row landed. Before classification it reads `pending`; after a successful `BUSINESS`, `PERSONAL`, or `MIXED` outcome it reads `reviewed`. Alongside this human block, the command emits a JSON envelope carrying the bucket identifier, the transaction identifier, the appended bucket-event identifiers, the review status, and the full updated transaction payload.

Expense rows take an optional `--category-id` from the deductible-expense taxonomy. List the valid identifiers first:

```
aeat app ledger categories
```

Then attach one to the classification:

```
aeat app ledger classify --id <transaction-prefix> --classification BUSINESS --category-id <category-id>
```

The `--category-id` value must come from that closed taxonomy; free text is refused. Income rows need no category.

### Allocate a mixed-use cost

Some costs serve both the business and your personal use - a phone line, a shared vehicle, part of the rent. For these, use `allocate` and state the business share as a fraction from 0 to 1. A half-business phone bill is `0.5`, not `50`:

```
aeat app ledger allocate --id <transaction-prefix> --business-pct 0.5 --category-id <category-id>
```

`allocate` derives the classification from the fraction: `1` becomes `BUSINESS`, `0` becomes `PERSONAL`, and any value between the two becomes `MIXED`. Don't pass `--classification` to `allocate` - it has no such flag. The confirmation block matches the one classify prints, and **Review status** reads `reviewed` again.

If you prefer to record a mixed split through `classify` instead, pass `--classification MIXED` with the matching `--business-pct`:

```
aeat app ledger classify --id <transaction-prefix> --classification MIXED --business-pct 0.5
```

`classify` accepts `--business-pct` only with `MIXED`. Passing it with any other classification is refused, and `MIXED` without `--business-pct` is refused too.

### Work through the quarter

Repeat classify and allocate for every transaction in the quarter. Use `classify` for the clear-cut rows - wholly-business expenses, personal ones, and income - and `allocate` for the genuinely shared costs. When every row reads `reviewed`, the quarter is labelled and ready for the readiness check in the next step.

To see every flag and its accepted values at any point, ask the verb itself:

```
aeat app ledger classify --help
aeat app ledger allocate --help
```

## Step 4: work the modelo with `aeat app modelo work`

With an active profile in place from the previous steps, you're ready to provision a work unit, enter your figures, and run the calculation. The `aeat app modelo work` command group is the data-entry and calculation surface for a single modelo. This step uses two verbs in sequence: `create` provisions the work unit, and `calculate` enters the data, runs the engine, and prints the casillas.

This tutorial files Modelo 130 (the quarterly self-assessment for self-employed taxpayers under direct estimation). It needs only two input figures, so you can complete the whole step without ingesting any transactions.

### Find the revision id

A work unit is keyed on four axes: the modelo, the year, the period, and the registry revision. You already know the first three. To find the revision id, describe the modelo:

```
aeat app modelo describe 130
```

The output lists the available revision ids for Modelo 130. Pick the one that covers your filing year. For this tutorial, that's `2019-y-siguientes`.

The revision id and the casillas a modelo exposes come from the registry and change between modelo versions. Always discover them with `aeat app modelo describe MODELO` rather than memorizing a value.

### Create the work unit

Provision the work unit with the four axes:

```
aeat app modelo work create --modelo 130 --year 2026 --period 1T --revision 2019-y-siguientes
```

The `--period` token names the filing window: `1T` through `4T` for quarters, `01` through `12` for months, and `0A` for an annual return. Modelo 130 is quarterly, so `1T` is the first quarter.

The output reports a status of `created` for a fresh work unit, or `reused` if one already exists for those four axes. `create` is idempotent on that key, so running it twice is safe.

The output also carries the **work unit id**, a 64-character identifier. Copy it from the output - you'll pass it to `calculate` in the next step. Any unambiguous prefix of the id works in place of the full string.

### Enter the data and calculate

Pass the work unit id as the first argument, then supply each figure with a repeatable `--casilla` option in `CASILLA=DECIMAL` form. For Modelo 130, casilla 01 holds your income and casilla 02 holds your deductible expenses:

```
aeat app modelo work calculate <WORK_UNIT_ID> --casilla 01=12000.00 --casilla 02=4000.00
```

Replace `<WORK_UNIT_ID>` with the id from the `create` output. To find the valid casilla ids for any modelo, run `aeat app modelo casillas 130`; the calculate error messages point you there too. A casilla accepts its id, its registry number, or the BOE printed number.

The command runs the engine, persists a new draft revision, and prints the result. Each run saves a fresh draft and never overwrites an earlier one, so you can recalculate as often as you like.

### Read the casillas

The default output is a tab-separated table. Reading top to bottom, you see:

- An `operation` line naming the command (`modelo.work.calculate`).
- The revision identity: the calculation revision id, the work unit id, the state, and the created and updated timestamps.
- A result-summary block.
- One `casilla` line per casilla, sorted by id. Input, bound, and computed casillas all appear, each as `casilla`, then the id, then the value.
- The deadline (plazo) lines for the period.
- A final confirmation sentence naming the `work revisions` and `work revision` verbs.

For Modelo 130 with income of 12000 and expenses of 4000, casilla 07 - the partial result of section I - comes out as `1600.00`. That figure is your evidence the engine ran correctly:

```
casilla	07	1600.00
```

The closing sentence confirms the save and points you to the resume and re-inspect verbs:

> Saved as draft calculation revision `<id>` (state: `<state>`). It is persisted and can be resumed later.

### Re-inspect without recalculating

The draft is persisted, so you can return to it any time. To list every calculation revision for a work unit:

```
aeat app modelo work revisions <WORK_UNIT_ID>
```

To show one stored revision's casillas without running the engine again:

```
aeat app modelo work revision <CALCULATION_REVISION_ID>
```

`aeat app modelo work status <WORK_UNIT_ID>` shows the work unit's metadata, including its four axes and current state.

### Read the machine-readable contract

For provenance or scripting, add the global `--format json` flag before the subcommand:

```
aeat --format json app modelo work calculate <WORK_UNIT_ID> --casilla 01=12000.00 --casilla 02=4000.00
```

JSON output returns the same calculation as a structured object. Two fields hold the casillas:

- `casilla_values` is a flat dictionary mapping each casilla id to its decimal value. Use it for a quick, human-readable view.
- `observations` is a typed list. Each entry carries the legal references (`legal_refs`) and source references (`source_refs`) behind a casilla. This is the authoritative provenance contract; the flat view is the convenience.

The object also includes `saved`, `saved_confirmation`, the revision identity fields, `binding_overrides`, `inputs_snapshot`, and `result_summary`. The data keys are the same whatever locale you run in.

### A note on scope

This step stays local on purpose. You build the modelo, calculate it, and inspect the draft - nothing leaves your machine. Verifying, marking a record as filed, and exporting come in later steps. `aeat app modelo work calculate` never submits anything to AEAT.

## Step 5: verify the computed declaration

You now have a calculation revision id from Step 4. Before you can export anything, the declaration has to pass verification. Verification checks the revision against the verified-complete contract: every required casilla resolved, every binding satisfied, and no blocking findings left open.

Run the verify verb with the revision id you saved in Step 4:

```
aeat app modelo work verify <calculation-revision-id>
```

Pass `--by` to record who signed off on the verification:

```
aeat app modelo work verify <calculation-revision-id> --by "Operator Name"
```

An active profile is required. If the command refuses with a no-active-profile message, return to Step 1 and select your profile first.

### Read the verdict

The command emits a verification report. The verdict lives in two fields:

- `completeness_status` - one of `complete`, `incomplete`, or `blocked`.
- `granted_verificado_completo` - `true` only when the status is `complete` and no blocking findings remain.

For a clean declaration, the report grants the verdict. The text output shows lines like these:

```
verification_report_id  <generated-id>
calculation_revision_id <calculation-revision-id>
completeness_status     complete
granted_verificado_completo     true
resolved_casilla_count  <n>
missing_required_casilla_count  0
finding_count   0
run_at  <iso-timestamp>
verified_by     Operator Name
```

The command exits with code 0, and the revision advances to the `verificado_completo` lifecycle state. This is the green light for the export step that follows.

For the machine-readable envelope (command `modelo.work.verify`), add the global `--format json` flag before the subcommand: `aeat --format json app modelo work verify <calculation-revision-id>`. The JSON carries the same verdict: `completeness_status` is `"complete"`, `granted_verificado_completo` is `true`, and the `findings` list is empty.

### When the verdict is refused

If your declaration isn't finished, the verdict comes back `incomplete` or `blocked`, `granted_verificado_completo` is `false`, and the command exits with code 1. Treat the non-zero exit as expected feedback, not a crash. The revision stays exactly as it was - verification never mutates a declaration it can't grant.

The report tells you what to fix. It lists each unresolved casilla and each finding. A finding row carries its kind, severity, the casilla involved, a message, and a next action. Findings also carry their `legal_refs` and `source_refs`, so you can trace every block back to its regulatory grounding. A trailing hint points you at the saved report:

```
next_action     aeat app modelo work verification-report list <calculation-revision-id>
```

To open that saved report, use the `verification-report` group, which lives directly under `aeat app modelo` (not under `work`):

```
aeat app modelo verification-report list <calculation-revision-id>
```

Resolve the missing casillas and blocking findings in your declaration, then run `aeat app modelo work verify` again with the same revision id.

### Re-inspect a saved report

Every verify run saves its report. To revisit a verdict without running verification again, list the reports for a revision and then view one by id:

```
aeat app modelo verification-report list <calculation-revision-id>
aeat app modelo verification-report view <verification-report-id>
```

Once the verdict reads `complete` and `granted_verificado_completo` is `true`, you're ready for Step 6: export the declaration for filing.

## Step 6: export the file you'll file yourself

You've produced the borrador with `aeat app modelo work calculate` and promoted it to a verified revision with `aeat app modelo work verify`. The verified revision is the only thing export accepts - a raw borrador is refused. This step turns that verified revision into a file you can upload, and shows you how to confirm exactly what was written.

### The app never files for you

Read this before you run the command: the app never submits to AEAT. It builds, validates, verifies, and exports. You upload the file yourself in the AEAT portal. Live submission is permanently forbidden across every command, so there is no flag, option, or hidden path that contacts AEAT. The export step is the last thing the app does; the filing is yours.

### Export the verified revision

Use `aeat app modelo export` with the work-unit id from your earlier steps and a path for the output file:

```
aeat app modelo export WORK_UNIT_ID --output borrador.boe
```

Replace `WORK_UNIT_ID` with the id emitted by your `work create`, `calculate`, and `verify` steps. It's a 64-character SHA-256 value; an unambiguous prefix works too. The `--output` option names where the file lands. Both the work-unit id and `--output` are required - omit `--output` and the command stops with a usage error before writing anything.

The command writes a local AEAT-compatible fichero-BOE file. It never contacts AEAT.

By default the export picks the work unit's most recent verified-complete or filed revision. To export a specific revision, name it:

```
aeat app modelo export WORK_UNIT_ID --output borrador.boe --revision REVISION_ID
```

A superseded revision is excluded from the default pick, so reach for `--revision` when you need one of those. To record who ran the export into the audit event, add a label:

```
aeat app modelo export WORK_UNIT_ID --output borrador.boe --by "your-name"
```

### Confirm what was produced

On success, the command exits 0, writes the file to your `--output` path, and prints a receipt. The receipt lists the operation, the work-unit id, the calculation-revision id, the bucket, the modelo, the filing year, the period, the output path, the byte size, the file's SHA-256 checksum, the format, and the bucket event id. A typed JSON payload carries the same fields.

Three fields confirm what landed on disk:

- `output_path` - where the file was written
- `byte_size` - how large it is
- `file_sha256` - the checksum of the exact bytes

The receipt carries a reference to the file plus its size and checksum, never the raw file contents. Use `file_sha256` to verify the file you upload to AEAT is the file the app produced.

### A note on language

As in earlier steps, the CLI renders in Spanish by default. The export help and messages read, for example, `Local; nunca contacta con AEAT`. For English, place the global `--language` flag before `app`:

```
aeat --language en app modelo export --help
```

The flag goes before the subcommand path. The `export` verb has no per-command language option - `aeat app modelo export --help --language en` errors with `No such option: --language`.

### If export refuses

Export refuses rather than write a broken file. In every case below, it exits non-zero and writes nothing:

- **The revision is still a draft.** Only verified-complete or filed revisions export. The message points you back: run `aeat app modelo work verify` first.
- **The work-unit id is unknown.** No matching work unit, no file.
- **The active profile is missing a required fact.** For modelo 111, that includes `identity.surnames`. Export names the missing fact instead of fabricating a placeholder. Fill it in your profile, then export again.
- **`--output` is missing.** A usage error stops the command before it writes.

### Don't confuse the internal filing mark with submission

`aeat app modelo work file CALCULATION_REVISION_ID` marks a revision as filed in your own records. It does not submit to AEAT - its own output says `internal only - does not submit to AEAT`. Use it only after you've uploaded the exported file in the AEAT portal yourself, to keep your local history straight.

## What you accomplished

You took one modelo from nothing to a filed revision and an AEAT-compatible file on disk. Along the way you ran five verbs:

- `aeat app modelo work create` opened a work unit for the period.
- `aeat app modelo work calculate` produced the calculated revision.
- `aeat app modelo work verify <revision>` printed a verification report and transitioned the revision to `verificado_completo`.
- `aeat app modelo work file <revision>` recorded the filing.
- `aeat app modelo export <work-unit> --output PATH` wrote the local fichero-BOE file.

Remember that nothing you did here reached AEAT: `work file` records the filing for your own history, `export` writes a local file, and you submit that file to AEAT yourself.

To confirm the end state, run `aeat config profile status` to see whether the active profile is configured and ready, and `aeat app overview status` to see workspace readiness and any remaining drafts or work units. Add `--period <P>` to `aeat app overview status` to narrow the view to a single period.

## If you get stuck

When a step fails or the output looks wrong, start with the diagnostics command:

```
aeat config repair
```

Run with no subcommand, it prints a full report covering your configuration, registry, profile, auth, and log health. The rest of the CLI already routes you here - a startup failure tells you to run `aeat config repair`.

For a targeted probe, reach for one of the focused subverbs:

- `aeat config repair connectivity` checks browser and AEAT Sede connectivity.
- `aeat config repair integrity registry` runs full registry validation.
- `aeat config repair integrity objects` verifies secure-object encryption tags.
- `aeat config repair logs` shows the log file path and recent lines.

A few exit codes signal where a step stopped. `aeat app modelo work verify` exits non-zero and leaves the revision unchanged when verification doesn't grant `verificado_completo`. `aeat config profile status` exits with code 2 when the active profile points at something that no longer exists. `aeat app modelo export` refuses and tells you to verify first when no verified-complete or filed revision exists.

To read any output as structured data, add `--format json` before the subcommand - for example, `aeat --format json app overview status`. Global flags (`--format`, `--language`, `--profile`, `--quiet`, `--verbose`, `--debug`) go before the subcommand, not after.

## Where to ask for help

Run bare `aeat` for the landing page. Its **More help** line and Quick start point you at the next surface:

- `aeat --help` for the full command tree.
- `aeat config --help` for configuration and diagnostics.
- `aeat app --help` for the modelo, ledger, and overview commands.

## Where to go next

- To repeat one part of this workflow on its own - recalculating a revision, exporting a fichero, checking connectivity - see the How-to recipes.
- To understand why the app stops at an internal filing and a local file, and never submits to AEAT, see the Explanation.
