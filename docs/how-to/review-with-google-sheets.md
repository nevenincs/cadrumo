# Review calculations with Google Sheets

This page covers the spreadsheet review of a modelo calculation: exporting it
to Google Sheets, checking how each total is reached with live formulas, and
pulling your reviewed edits back so the tool records them against your
filing. This workflow is for reviewing calculated values after your profile
and transactions are ready. It is not a bank statement import or bulk edit
tool.

Google Sheets is the review surface. The tool can also produce an offline
`.xlsx` file, but that file is a fixed record of the calculation and its
supporting evidence, a copy you can keep, not an editable review tool: it
does not recompute, and there is no way to edit it and feed changes back.
Use Google Sheets when you want to review and adjust.

Every `config google` command on this page reaches Google Drive and Sheets, so
they run against your own authorized account rather than the documentation
sandbox. They are shown as display-only frames. The local readiness checks at
the end run live at build time.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Import and manage transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- a Google API credentials file (a Desktop OAuth client JSON from the
  [Google Cloud Console](https://console.cloud.google.com/))
- the ID of a Google Drive folder where Cadrumo should create spreadsheets
  (copy the ID from the folder's URL in Google Drive)

Cadrumo creates its `cadrumo-vault/` folder inside that Drive folder. It does
not use an older `aeat-vault/` folder; export a new workbook before pulling
edits into Cadrumo.

## Configure Google access

Register the Desktop OAuth client for the active profile, run the consent flow,
and set the Drive folder where Cadrumo will create spreadsheets:

```{cli-sequence} sheets-configure
@step Register the Desktop OAuth client for the active profile.
@static aeat config google register --client-json ./client_secret.json
@step Run the Google consent flow and confirm the status.
@static aeat config google login
@static aeat config google status
@step Set and confirm the Drive folder, then probe the connection.
@static aeat config google folder set <drive-folder-id>
@static aeat config google folder get
@static aeat config google sync probe
```

The Google integration is profile-scoped. If you switch profiles, check Google
status and folder binding again.

## Export a calculation workbook

Export the registry calculation surface for one modelo, year, and period. The
export creates a Google Sheets workbook inside the configured `cadrumo-vault/`
area in Drive:

```{cli-sequence} sheets-export
@step Export the calculation surface for one modelo, year, and period.
@static aeat config google sync calc export --modelo 303 --year 2026 --period 1T
```

It is a calculation review surface, not a bank statement export. Use `aeat app
ledger export` when you need a CSV, JSONL, or XLSX snapshot of ledger rows.

Use `--prefill-relations` only when you want the spreadsheet to include values
carried from related filings, such as annual summaries or prior-quarter
carryovers.

## Pull your edits back

After reviewing or editing the workbook, pull typed edits back from the Sheet.
Add `--assemble-observations` when you want edited row-level data saved back
as structured observations:

```{cli-sequence} sheets-pull
@step Pull typed edits back from the reviewed spreadsheet.
@static aeat config google sync calc pull --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id>
```

The pull command checks that the spreadsheet belongs to the current profile and
matches the expected filing period. If it refuses, re-export and retry from the
new spreadsheet.

## Compute casilla values from the Sheet

Run `compute` when you want Cadrumo to calculate casilla values from the edits
in the Sheet. It pulls the operator-edited cells, runs the calculation engine
over them, and displays the result. It persists nothing:

```{cli-sequence} sheets-compute
@step Compute casilla values from the operator-edited cells.
@static aeat config google sync calc compute --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id>
```

The compute command checks that the spreadsheet matches the expected filing
period. If it refuses, re-export and retry from the new spreadsheet.

## Check the spreadsheet calculation

Run the calc-sheets verification command for the same modelo, year, and period.
If you have a scenario JSON with operator inputs and expected Agencia Estatal
de Administración Tributaria (AEAT) outputs, pass it explicitly with
`--scenario`:

```{cli-sequence} sheets-verify
@step Verify the spreadsheet calculation for the modelo, year, and period.
@static aeat config google sync calc verify --modelo 303 --year 2026 --period 1T
@step Verify against an explicit scenario JSON of inputs and expected outputs.
@static aeat config google sync calc verify --modelo 303 --year 2026 --period 1T --scenario ./scenario.json
```

Verification compares the calculation surfaces implemented by the app. It does
not submit a filing to AEAT.

## Back up your encrypted records to Drive

Keep an off-machine copy of your encrypted records by mirroring them to the
configured Drive folder. Preview with `--dry-run` first; it reports what would
upload per storage area without changing anything. Narrow a large push with
`--namespace` or `--limit`:

```{cli-sequence} sheets-backup-push
@step Preview the encrypted backup to Drive without uploading.
@static aeat config google sync push --dry-run
@step Mirror the encrypted records to the Drive folder.
@static aeat config google sync push
```

Only ciphertext is uploaded. Your records leave the machine exactly as they
sit encrypted on disk, and the master key never leaves your computer, so the
Drive copy is unreadable without it. The mirror is one-way: Cadrumo writes the
copy and never reads Drive back as a source of truth for your records.

## Sign out of Google

Clear the Google session for the active profile. Logout removes the saved
session token and its metadata. The registered OAuth client is kept on purpose,
so a later `aeat config google login` can sign in again without re-importing
the Cloud Console JSON:

```{cli-sequence} sheets-logout
@step Clear the Google session for the active profile.
@static aeat config google logout
```

## Where this fits

Use this after transaction review and classification. Confirm the period is
ready before you rely on the calculation workbook:

```{cli-sequence} sheets-readiness
:verify: Confirm the period's readiness before relying on the workbook.
@step Import a quarter so there is data to check.
@setup aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Run the period preflight.
aeat app ledger preflight --year 2026 --period 1T
@step Read the overall ledger state for the period.
@result aeat --format json app ledger status --year 2026 --period 1T
@expect exit_code == 0
```

If the ledger still has missing categories, IVA fields, currency, or
proportionality references, finish those in
[Classify transactions](classify-transactions.md) before relying on the
calculation workbook.

For casilla-level manual inputs, bindings, offsets, and revisions, use
[Review and supply calculation inputs](review-calculation-values.md).

## Next steps

- [Import and manage transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
