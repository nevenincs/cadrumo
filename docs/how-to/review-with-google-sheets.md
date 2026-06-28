# Review calculations with Google Sheets

Use this guide when you want to review a modelo calculation in a Google Sheets
spreadsheet. This workflow is for reviewing calculated values after your profile
and transactions are ready. It is not a bank statement import or bulk edit tool.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Work with Transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- a Google API credentials file (a Desktop OAuth client JSON from the
  [Google Cloud Console](https://console.cloud.google.com/))
- the ID of a Google Drive folder where `aeat` should create spreadsheets
  (copy the ID from the folder's URL in Google Drive)

## Configure Google access

Register the Desktop OAuth client for the active profile:

```bash
aeat config google register --client-json ./client_secret.json
```

Run the Google consent flow:

```bash
aeat config google login
aeat config google status
```

Set the Drive folder where `aeat` will create spreadsheets:

```bash
aeat config google folder set <drive-folder-id>
aeat config google folder get
aeat config google sync probe
```

The Google integration is profile-scoped. If you switch profiles, check Google
status and folder binding again.

## Export a calculation workbook

Export the registry calculation surface for one modelo, year, and period:

```bash
aeat config google sync calc export --modelo 303 --year 2026 --period 1T
```

The export creates a Google Sheets workbook inside the configured `aeat-vault/`
area in Drive. It is a calculation review surface, not a bank statement export.
Use `aeat app ledger export` when you need a CSV, JSONL, or XLSX snapshot of
ledger rows.

Use `--prefill-relations` only when you want the spreadsheet to include values
carried from related filings, such as annual summaries or prior-quarter
carryovers.

## Pull operator edits

After reviewing or editing the workbook, pull typed edits back from the Sheet:

```bash
aeat config google sync calc pull --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id>
```

Add `--assemble-observations` when you want edited row-level data saved back
as structured observations.

The pull command checks that the spreadsheet belongs to the current profile and
matches the expected filing period. If it refuses, re-export and retry from the
new spreadsheet.

## Compute casilla values from the Sheet

Run `compute` when you want `aeat` to calculate casilla values from the edits
in the Sheet. It pulls the operator-edited cells, runs the calculation engine
over them, and displays the result. It persists nothing.

```bash
aeat config google sync calc compute --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id>
```

The compute command checks that the spreadsheet matches the expected filing
period. If it refuses, re-export and retry from the new spreadsheet.

## Verify the calculation surface

Run the calc-sheets verification command for the same modelo, year, and period:

```bash
aeat config google sync calc verify --modelo 303 --year 2026 --period 1T
```

If you have a scenario JSON with operator inputs and expected AEAT outputs,
pass it explicitly:

```bash
aeat config google sync calc verify --modelo 303 --year 2026 --period 1T --scenario ./scenario.json
```

Verification compares the calculation surfaces implemented by the app. It does
not submit a filing to AEAT.

## Mirror encrypted records to Drive

Keep an off-machine copy of your encrypted records by mirroring them to the
configured Drive folder:

```bash
aeat config google sync push --dry-run
aeat config google sync push
```

Preview with `--dry-run` first; it reports what would upload per storage
area without changing anything. Narrow a large push with `--namespace` or
`--limit`.

Only ciphertext is uploaded — your records leave the machine exactly as they
sit encrypted on disk, and the master key never leaves your computer, so the
Drive copy is unreadable without it. The mirror is one-way: aeat writes the
copy and never reads Drive back as a source of truth for your records.

## Sign out of Google

Clear the Google session for the active profile:

```bash
aeat config google logout
```

Logout removes the saved session token and its metadata. The registered
OAuth client is kept on purpose, so a later `aeat config google login` can
sign in again without re-importing the Cloud Console JSON.

## Where this fits

Use this after transaction review and classification:

```bash
aeat app ledger preflight --year 2026 --period 1T
aeat app ledger status --year 2026 --period 1T
```

If the ledger still has missing categories, IVA fields, currency, or
proportionality references, finish those in
[Classify transactions](classify-transactions.md) before relying on the
calculation workbook.

For casilla-level manual inputs, bindings, offsets, and revisions, use
[Review and supply calculation inputs](review-calculation-values.md).

## Next steps

- [Work with Transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
