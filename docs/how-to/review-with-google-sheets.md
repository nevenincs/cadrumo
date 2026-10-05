# Review calculations with Google Sheets

This page covers the spreadsheet review of a modelo calculation: exporting it
to Google Sheets, checking how each total is reached with live formulas, and pulling your reviewed edits back as filing inputs. Pull returns those edits without saving them. This workflow is for reviewing calculated values after your profile
and transactions are ready. It is not a bank statement import or bulk edit
tool.

Cadrumo has two spreadsheet routes for the same calculation surface.
`aeat app modelo spreadsheet push` creates a Google Sheets workbook in your
Drive, and `pull` and `calculate` read your edits back. `aeat app modelo
spreadsheet export` writes an offline `.xlsx` workbook with live formulas to a
local path. It needs no Google account, but no command reads an edited local
workbook back. Use Google Sheets to review and adjust, and see
[Export an offline workbook](#export-an-offline-workbook) for the other route.

The local configuration commands on this page (status, folder view, logout) and the readiness checks on your records run live at build time. The commands that reach
Google Drive and Sheets run against your own authorized account rather than the
documentation sandbox, so they are shown as examples that are not run.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Import and manage transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- the `google` extra, installed with `pip install "cadrumo[google]"`

Cadrumo works only inside a folder it creates in your Google Drive when you
sign in. It never opens, lists or changes a file or folder you already had,
and no command accepts a Drive folder or file from you, apart from the ID of
a workbook Cadrumo itself exported. It does not use an older `aeat-vault/`
folder; export a new workbook before pulling edits into Cadrumo.

## Configure Google access

Sign in to Google for the active profile. Cadrumo opens Google's consent page
in your browser and asks for your email address and for access to the files
it creates, nothing else in your Drive. You do not need a Google Cloud project
or a credentials file. Signing in also creates one folder in your My Drive,
named `Cadrumo` followed by the first characters of the profile's ID, where
every exported workbook and the encrypted backup are kept. Sign-in reaches
Google, so it is shown here without being run:

```{cli-sequence} sheets-oauth
```

Check the Google status and the folder created for the profile. These are
local commands, so they run here. On a profile that has not signed in, the
status shows `session_present` as false and no folder exists yet:

```{cli-sequence} sheets-folder
:verify: Confirm that a profile which has not signed in has no Drive folder.
```

If you move the folder to the bin, or sign in to a different Google account,
sign in again: Cadrumo finds its folder or creates a new one, and you export
your workbooks again.

Probe the connection once you have signed in. The probe reaches
Google, so it is shown here without being run:

```{cli-sequence} sheets-probe
```

The Google integration is profile-scoped. Each profile signs in separately and gets its own folder.

## Export a calculation workbook

Export the calculation of one modelo, year, and period. The
export creates a Google Sheets workbook inside the configured `cadrumo-vault/`
area in Drive:

```{cli-sequence} sheets-push
```

It is a workbook for reviewing a calculation, not a bank statement export. Use `aeat app
ledger export` when you need a CSV, JSONL, or XLSX snapshot of your records.

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

The result prints the file path, size, SHA-256 checksum, and box count. The
command refuses to overwrite an existing file unless you add `--replace`, and
it refuses an `--output` path whose parent directory does not exist. The
refusal reads `The export output path is not valid` and names the reason.

The offline workbook is a review copy. `pull`, `calculate`, and `verify` work
only with a Google Sheet, so edits you make in the local file do not flow back
into Cadrumo. It accepts `--prefill-relations` like `push`.

## Pull your edits back

After reviewing or editing the workbook, pull your edits back from the Sheet.
Add `--assemble-observations` when you want the command output to include
edited row-level data assembled as structured observations. The command does not save those observations:

```{cli-sequence} sheets-pull
```

The pull command checks that the spreadsheet belongs to the current profile and
matches the expected filing period. If it refuses, re-export and retry from the
new spreadsheet. To use a pulled edit in a filing, supply it to `aeat app modelo
work calculate` with `--casilla`, `--binding`, or `--relation`.

(compute-casilla-values-from-the-sheet)=
## Compute box values from the Sheet

Run `aeat app modelo spreadsheet calculate` when you want Cadrumo to calculate
box values from the edits in the Sheet. It pulls the cells you edited, runs the calculation engine
over them, and displays the result. It saves nothing:

```{cli-sequence} sheets-calculate
```

The `calculate` command checks that the spreadsheet matches the expected filing
period. If it refuses, re-export and retry from the new spreadsheet.

## Check the spreadsheet calculation

Run the spreadsheet check command for the same modelo, year, and period. If you have a scenario JSON with your inputs and expected Agencia Estatal
de Administración Tributaria (AEAT) outputs, pass it explicitly with
`--scenario`:

```{cli-sequence} sheets-verify
```

The check rewrites that period's workbook with your scenario file's inputs,
then compares the workbook's formula results with the local calculation engine
and, when the scenario supplies AEAT-published expected outputs, with those as
well. It overwrites edits made in the pushed sheet, so pull your edits before
you run the check.
It does not submit a filing to AEAT.

(back-up-your-encrypted-records-to-drive)=
## Back up your encrypted data to Drive

Keep an off-machine copy of your encrypted data by mirroring it to the
configured Drive folder. Preview with `--dry-run` first; it reports what would
upload per storage area without changing anything. Narrow a large push with
`--namespace` or `--limit`:

```{cli-sequence} sheets-backup-push
```

Only encrypted data is uploaded. Your data leaves the machine exactly as it
sits encrypted on disk, and the master key never leaves your computer, so the
Drive copy is unreadable without it. The mirror is one-way: Cadrumo writes the
copy and never reads Drive back as the original of your data.

## Sign out of Google

Clear the Google session for the active profile. Logout is a local command, so
it runs here. If a session exists, it removes the saved session token and its
metadata. The profile's Drive folder is kept, so a later `aeat config google
login` signs in again and finds it:

```{cli-sequence} sheets-logout
:verify: Confirm that with no saved session logout removes nothing.
```

## Upgrading from an earlier version

Earlier versions asked you to create a Google Cloud project, register its
client file, and point Cadrumo at a Drive folder of your own. This version
does none of that. After you update:

1. Run `aeat config google login`. A sign-in from an earlier version is not
   reused; Cadrumo tells you to sign in again.
2. Export your workbooks again. Cadrumo keeps everything in the folder it
   creates at sign-in and does not look for workbooks or folders an earlier
   version created. Those stay in your Drive untouched; move or delete them
   yourself.

These are no longer available:

| Removed | Use instead |
|---|---|
| `aeat config google register` and its client file | Nothing. The application carries its own Google client. |
| `aeat config google credential-source` and service-account access | `aeat config google login` |
| `aeat config google folder set` and `CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID` | Nothing. Cadrumo creates its folder at sign-in. |
| `aeat config google login --refresh-only` | `aeat config google login` |
| `aeat app ledger evidence pull` and `pull-all` | Download the document, then `aeat app ledger evidence add`; see [Attach supporting documents](ledger-evidence.md). |
| `CADRUMO_GOOGLE_OAUTH_ACCESS_REFRESH_BUFFER_S` | Nothing. It had no effect. |

Scripts that read command output should also note these changes. `config
google status` no longer reports `client_registered`, `client_id`,
`last_refresh_at` or `reauth_required`. `config google logout` no longer
reports `client_preserved`. `config google login` no longer reports `mode` and
now reports `root_folder_id`. The error codes `AUTH_GOOGLE_EXPIRED` and
`AUTH_GOOGLE_REVOKED` are replaced by `REFUSED_GOOGLE_SIGN_IN_REQUIRED`, and a
profile whose installation has no Google client refuses with
`REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE`.

## Where this fits

Use this after transaction review and classification. Confirm the period is
ready before you rely on the calculation workbook:

```{cli-sequence} sheets-readiness
:verify: Confirm the preflight reports the imported rows as not ready for calculation.
```

If your records still have missing categories, VAT fields, currency, or
proportionality references, finish those in
[Classify transactions](classify-transactions.md) before relying on the
calculation workbook.

For manual box values, the rules that fill each box, offsets, and earlier
calculations, use
[Review and supply calculation inputs](review-calculation-values.md).

## Next steps

- [Import, export, and supporting documents](../reference/import-export-and-evidence.md) -
  understand why a Google Sheet is for review only, not filing proof or the
  official basis of a calculation.
- [Import and manage transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
