# Review calculations with Google Sheets

This page covers the spreadsheet review of a modelo calculation: exporting it
to Google Sheets, checking how each total is reached with live formulas, and
pulling your reviewed edits back as typed filing inputs. Pull returns those
edits without persisting them. This workflow is for reviewing calculated values after your profile
and transactions are ready. It is not a bank statement import or bulk edit
tool.

Cadrumo has two spreadsheet routes for the same calculation surface.
`aeat app modelo spreadsheet push` creates a Google Sheets workbook in your
Drive, and `pull` and `calculate` read your edits back. `aeat app modelo
spreadsheet export` writes an offline `.xlsx` workbook with live formulas to a
local path. It needs no Google account, but no command reads an edited local
workbook back. Use Google Sheets to review and adjust, and see
[Export an offline workbook](#export-an-offline-workbook) for the other route.

The local configuration commands on this page (status, folder binding, logout)
and the ledger readiness checks run live at build time. The commands that reach
Google Drive and Sheets run against your own authorized account rather than the
documentation sandbox, so they are shown as display-only frames.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Import and manage transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- the `google` extra, installed with `pip install "cadrumo[google]"`
- a Google API credentials file (a Desktop OAuth client JSON from the
  [Google Cloud Console](https://console.cloud.google.com/))
- the ID of a Google Drive folder where Cadrumo should create spreadsheets
  (copy the ID from the folder's URL in Google Drive)

Cadrumo creates its `cadrumo-vault/` folder inside that Drive folder. It does
not use an older `aeat-vault/` folder; export a new workbook before pulling
edits into Cadrumo.

## Configure Google access

Register the Desktop OAuth client for the active profile and run the consent
flow. Both reach Google, so they are display-only here:

```{cli-sequence} sheets-oauth
```

Check the Google status and set the Drive folder where Cadrumo will create
spreadsheets. These are local configuration commands, so they run here. On an
unconfigured profile the status shows `client_registered` and `session_present`
as false, and the folder you set reads back verbatim:

```{cli-sequence} sheets-folder
:verify: Confirm the Drive folder binding reads back the value you set.
```

Probe the connection once the OAuth client is registered. The probe reaches
Google, so it is display-only here:

```{cli-sequence} sheets-probe
```

The Google integration is profile-scoped. If you switch profiles, check Google
status and folder binding again.

## Export a calculation workbook

Export the registry calculation surface for one modelo, year, and period. The
export creates a Google Sheets workbook inside the configured `cadrumo-vault/`
area in Drive:

```{cli-sequence} sheets-push
```

It is a calculation review surface, not a bank statement export. Use `aeat app
ledger export` when you need a CSV, JSONL, or XLSX snapshot of ledger rows.

Use `--prefill-relations` only when you want the spreadsheet to include values
carried from related filings, such as annual summaries or prior-quarter
carryovers. Add `--dry-run` to preview what the export would clear and rewrite
in the workbook without writing anything.

(export-an-offline-workbook)=
## Export an offline workbook

To review without Google, write the same calculation surface to a local `.xlsx`
workbook with live formulas. Nothing is uploaded:

```text
aeat app modelo spreadsheet export --modelo 303 --year 2026 --period 1T --output modelo-303-2026-1T.xlsx
```

The result prints the file path, size, SHA-256 checksum, and casilla count. The
command refuses to overwrite an existing file unless you add `--replace`, and
it refuses an `--output` path whose parent directory does not exist. The
refusal reads `The export output path is not valid` and names the reason.

The offline workbook is a review copy. `pull`, `calculate`, and `verify` work
only with a Google Sheet, so edits you make in the local file do not flow back
into Cadrumo. It accepts `--prefill-relations` like `push`.

## Pull your edits back

After reviewing or editing the workbook, pull typed edits back from the Sheet.
Add `--assemble-observations` when you want the command output to include
edited row-level data assembled as structured observations. The command does
not persist those observations:

```{cli-sequence} sheets-pull
```

The pull command checks that the spreadsheet belongs to the current profile and
matches the expected filing period. If it refuses, re-export and retry from the
new spreadsheet. To use a pulled edit in a filing, supply it to `aeat app modelo
work calculate` with `--casilla`, `--binding`, or `--relation`.

## Compute casilla values from the Sheet

Run `aeat app modelo spreadsheet calculate` when you want Cadrumo to calculate
casilla values from the edits in the Sheet. It pulls the operator-edited cells, runs the calculation engine
over them, and displays the result. It persists nothing:

```{cli-sequence} sheets-calculate
```

The `calculate` command checks that the spreadsheet matches the expected filing
period. If it refuses, re-export and retry from the new spreadsheet.

## Check the spreadsheet calculation

Run the calc-sheets verification command for the same modelo, year, and period.
If you have a scenario JSON with operator inputs and expected Agencia Estatal
de Administración Tributaria (AEAT) outputs, pass it explicitly with
`--scenario`:

```{cli-sequence} sheets-verify
```

Verification rewrites that period's workbook with your scenario file's inputs,
then compares the workbook's formula results with the local calculation engine
and, when the scenario supplies AEAT-published expected outputs, with those as
well. It overwrites edits made in the pushed sheet, so pull your edits before
you verify.
It does not submit a filing to AEAT.

## Back up your encrypted records to Drive

Keep an off-machine copy of your encrypted records by mirroring them to the
configured Drive folder. Preview with `--dry-run` first; it reports what would
upload per storage area without changing anything. Narrow a large push with
`--namespace` or `--limit`:

```{cli-sequence} sheets-backup-push
```

Only ciphertext is uploaded. Your records leave the machine exactly as they
sit encrypted on disk, and the master key never leaves your computer, so the
Drive copy is unreadable without it. The mirror is one-way: Cadrumo writes the
copy and never reads Drive back as a source of truth for your records.

## Sign out of Google

Clear the Google session for the active profile. Logout is a local command, so
it runs here. If a session exists, it removes the saved session token and its
metadata. The registered OAuth client is kept on purpose, so a later `aeat
config google login` can sign in again without re-importing the Cloud Console
JSON:

```{cli-sequence} sheets-logout
:verify: Confirm logout keeps the registered client; with no saved session it removes nothing.
```

## Where this fits

Use this after transaction review and classification. Confirm the period is
ready before you rely on the calculation workbook:

```{cli-sequence} sheets-readiness
:verify: Confirm the preflight reports the imported rows as not ready for calculation.
```

If the ledger still has missing categories, IVA fields, currency, or
proportionality references, finish those in
[Classify transactions](classify-transactions.md) before relying on the
calculation workbook.

For casilla-level manual inputs, bindings, offsets, and revisions, use
[Review and supply calculation inputs](review-calculation-values.md).

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  understand why a Google Sheet is a review surface rather than filing evidence
  or calculation authority.
- [Import and manage transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
