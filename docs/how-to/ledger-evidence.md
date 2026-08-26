# Attach invoices and receipts to ledger transactions

Store an evidence record for each invoice or receipt and link it to the transaction it supports. Checks, exports, and year-end reviews can then point at the document behind every number. Stored evidence remains under encrypted local custody. Google Drive pull commands reach your authorized account before storing the downloaded bytes locally.

## Before you start

You need:

- An active taxpayer profile. Evidence is stored under the active profile; if none is set, the command refuses. See [Set up your taxpayer profile](profile-setup.md).
- A master-key passphrase. The tool prompts for it the first time it opens your encrypted storage in a session.
- Transactions in your ledger. If your ledger is empty, see [Import and manage transactions](import-bank-statements.md) first.
- The invoice or receipt as a PDF or image file. Cadrumo copies the file's bytes into encrypted storage together with the facts you type, plus a content fingerprint and the original location as provenance. Your original file is never needed again after `add`.

## Add an evidence record

Record the invoice file and its details, then view the stored record. The file
path is the only required part; every metadata flag is optional. `--iva-rate 21`
means 21 %:

```{cli-sequence} ledger-evidence-add
:verify: Confirm the evidence record stored the supplier and invoice details.
```

The command prints the evidence ID. Note the full ID down - later commands need it. Add what you know now; update the rest later.

## Attach an evidence record to a transaction

Attach the evidence record to the transaction it supports. The sequence records
an evidence file and an expense, then attaches one to the other:

```{cli-sequence} ledger-evidence-attach
:verify: Confirm the purchase-invoice evidence attached to the transaction.
```

A transaction carries at most one purchase-invoice evidence record. The command refuses a second one, and refuses re-attaching the same one.

Do not reach for `aeat app ledger link` here. `attach` and `link` are different operations on the same transaction: `attach` carries the evidence document, while `link` binds the transaction to an invoice and requires `--invoice-id`. That id comes from an imported, reconciled, or manually added invoice - the id `aeat app ledger invoice add` prints is exactly the one to pass.

For most receipts and invoices, `--purchase-invoice-evidence-id` above is the path to use; the evidence id comes straight from `evidence add`.

The `attach` command also has an `--attachment-id` option (repeatable) for a generic secure attachment that does not carry the purchase-invoice role. It expects the 64-character content id of a blob already in encrypted attachment storage, and it refuses any id that has no stored blob (`attachment_ids must reference existing secure attachment manifests and blobs`). No operator command currently prints that 64-character id - the `evidence_id` from `evidence add` is a different, shorter id and is not accepted here. Until a command surfaces the attachment id, use `--purchase-invoice-evidence-id` or `evidence pull` instead.

## Pull a document from Google Drive instead

When the document lives in Google Drive, pull it straight into encrypted evidence storage. This command reaches Google Drive, so it runs against your own authorized account rather than in the documentation sandbox:

```{cli-sequence} ledger-evidence-pull
```

The command downloads the Drive file, stores its bytes encrypted with the transaction, and keeps the original link as provenance. Evidence always carries the document itself, never a bare link: Gmail links, arbitrary URLs, and Drive files outside the granted scope are refused. For a refused source, download the document yourself and attach it with `aeat app ledger evidence add` or `aeat app ledger attach --attachment-id`.

## Bulk-fetch every invoice in a Drive folder

Fetch every PDF and image invoice in one Drive folder at once, instead of one document at a time. Like `evidence pull`, this command reaches Google Drive and runs against your own authorized account:

```{cli-sequence} ledger-evidence-pull-all
```

The command lists the folder's contents, downloads each PDF or image, and stores every file as encrypted evidence. Fetched files are not linked to a transaction yet; bind each one afterward with `aeat app ledger attach --attachment-id <attachment-id>`.

Re-run the same command any time. A file already fetched is recognized by its content and is not stored twice. A file outside the granted Drive scope is refused individually and does not stop the rest of the sweep; download it yourself and attach it with `aeat app ledger attach --attachment-id`.

Gmail bulk-fetch is not available yet.

## Invoice records are a separate feature

An invoice *record* - who owes whom, for what amount - is not a stored
document. [Manage business invoices](manage-invoices.md) owns invoice
records: registering issued and received invoices, the reconciliation
catalogue, and linking a catalogue invoice to the transaction that settles
it. This page is about the documents - PDFs and images - you store as
evidence and link to transactions.

## List, view, update, and remove evidence records

List every stored record, view one in full, update its details, and remove one
you no longer need. The sequence records an evidence file, lists and inspects
it, changes the supplier, and confirms the change:

```{cli-sequence} ledger-evidence-manage
:verify: Confirm the evidence record's supplier was updated.
```

Remove an evidence record you no longer need, addressing it by id:

```{cli-sequence} ledger-evidence-remove
:verify: Confirm the evidence record no longer appears in the catalogue.
```

Removing applies to evidence records, not transactions. To fix a transaction row itself, see [Correct mistakes in your ledger](correct-ledger-entries.md).

## After you correct a row

If you merge or split transactions, check the new rows and re-attach evidence where needed. [Correct mistakes in your ledger](correct-ledger-entries.md) covers row changes.

## Where evidence shows up

Ledger exports include the evidence link with each transaction. Ledger-derived calculations carry the evidence trail through to filing artifacts.

Read [Import, export, and evidence](../reference/import-export-and-evidence.md)
for the difference between linked ledger evidence, an AEAT upload file,
official filing proof, and an audit bundle.

## Where to get help

- If a command fails or refuses, see [Troubleshooting](troubleshooting.md).
- If a term is unfamiliar, see the {doc}`Glossary </_generated/glossary>`.
- Before sharing command output with anyone, strip tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) - understand how evidence participates in calculation, filing, and audit.
- [Import and manage transactions](import-bank-statements.md) - bring more transactions into the ledger.
- [Correct mistakes in your ledger](correct-ledger-entries.md) - fix mistakes in transaction rows.
- [Classify transactions](classify-transactions.md) - assign tax categories to your transactions.
- [CLI reference](../cli/index.rst) - the full command surface.
