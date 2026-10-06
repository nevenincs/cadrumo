# Review calculations with Google Sheets

Google review is outbound-only. Edits in Google Sheets do not become Cadrumo
calculation inputs. The spreadsheet `pull`, `calculate`, and `verify` commands
have been removed; use local calculation inputs and `work calculate` instead.

The previous template-based Google `push` remains disabled. Use `publish` with
an exact saved calculation revision to create a new native Google Sheet.
Offline `.xlsx` export remains available; see
[Export an offline workbook](#export-an-offline-workbook).

The local configuration commands on this page (status, folder view, logout) and the readiness checks on your records run live at build time. The commands that reach
Google Drive and Sheets run against your own authorized account rather than the
documentation sandbox, so they are shown as examples that are not run.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Import and manage transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- the `google` extra, installed with `pip install "cadrumo[google]"`

Cadrumo creates a managed Drive folder for each profile. Transport checks the
local creation receipt, profile, ownership markers and current ancestry before
accessing managed content. Known identities may receive a minimal metadata check
when moved outside that folder; their content is then refused. Google does not
provide an atomic folder-membership condition for every content request, so an
external move between the check and request remains a provider limitation.

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

A trashed or mismatched managed folder is refused. Signing in again does not
search your Drive for a same-name replacement. An uncertain creation needs
reconciliation before another creation attempt.

Probe the connection once you have signed in. The probe reaches
Google, so it is shown here without being run:

```{cli-sequence} sheets-probe
```

The Google integration is profile-scoped. Each profile signs in separately and gets its own folder.

## Publish a saved calculation

Copy the calculation revision ID returned by `app modelo work calculate`, then run:

```text
aeat app modelo spreadsheet publish --calculation-revision-id REVISION_ID --accept-readable-export
```

The flag authorizes a readable copy of that revision and its captured ledger
support in the profile's managed Google folder. Anyone with sufficient Google
authorization can read the Sheet. Original attachment bytes are not uploaded by
this command. The result includes the actual spreadsheet URL.

Each publication creates a new document and preserves earlier review notes.
The Sheet uses saved values without recalculating from today's ledger. Missing
historical evidence, attribution or display metadata is reported explicitly;
an incomplete review is not a filing-ready or audit-complete declaration.

An optional `--publication-id UUID` identifies one publication across retries.
Keep that identity after a timeout: a timeout does not prove that no Sheet was
created. A retained, completed publication can return its existing URL without
rewriting it; partial or uncertain publication requires reconciliation.

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

The offline workbook is a review copy. Edits in it do not flow back into
Cadrumo. It accepts `--prefill-relations` for values carried from related filings.

(back-up-your-encrypted-records-to-drive)=
## Back up your encrypted data to Drive

Keep an off-machine copy of your encrypted data by mirroring it to the
configured Drive folder. Preview with `--dry-run` first; it reports what would
upload per storage area without changing anything. Narrow a large push with
`--namespace` or `--limit`:

```{cli-sequence} sheets-backup-push
```

Secure-object payloads are uploaded as their stored ciphertext, with length
and SHA-256 checks before a complete namespace manifest is published. Structural
manifests contain metadata and are not encrypted payloads. A limited or incomplete
upload does not establish a complete backup; inspect failed and degraded manifest
counts. A partial upload retains acknowledged ciphertext when safe cleanup cannot
be established.

This is a one-way mirror with no remote restore command. Local `archive import`
reads a portable archive, not these mirrored objects. Successful upload and
integrity verification do not establish recoverability.

## Sign out of Google

Google logout removes local credentials; it does not revoke Google's grant.
To stop access by copied credentials as well, follow
[Remove Google access](protect-data-access.md#remove-google-access).

Clear the Google session for the active profile. Logout is a local command, so
it runs here. If a session exists, it removes the saved session token and its
metadata. The profile's Drive folder is kept, so a later `aeat config google
login` signs in again and validates its recorded identity:

```{cli-sequence} sheets-logout
:verify: Confirm that with no saved session logout removes nothing.
```

## Upgrading from an earlier version

Earlier versions asked you to create a Google Cloud project, register its
client file, and point Cadrumo at a Drive folder of your own. This version
does none of that. After you update:

1. Run `aeat config google login`. A sign-in from an earlier version is not
   reused; Cadrumo tells you to sign in again.
2. Keep earlier workbooks for review. Cadrumo does not adopt historical
   unreceipted workbooks or search Drive to repair them. Use `publish` to make a
   new review copy from a saved calculation revision.

These are no longer available:

| Removed | Use instead |
|---|---|
| `config google register` and its client file | Nothing. The application carries its own Google client. |
| `config google credential-source` and service-account access | `aeat config google login` |
| `config google folder set` and `CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID` | Nothing. Cadrumo creates its folder at sign-in. |
| `config google login --refresh-only` | `aeat config google login` |
| `app ledger evidence pull` and `pull-all` | Download the document, then `aeat app ledger evidence add`; see [Attach supporting documents](ledger-evidence.md). |
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
