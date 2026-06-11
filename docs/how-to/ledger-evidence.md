# Attach invoices and receipts to ledger transactions

Store an evidence record for each invoice or receipt and link it to the transaction it supports. Checks, exports, and year-end reviews can then point at the document behind every number. Everything happens on your computer - nothing is uploaded or sent anywhere.

## Before you start

You need:

- Transactions in your ledger. If your ledger is empty, see [Work with transactions](import-bank-statements.md) first.
- The invoice or receipt as a PDF or image file. aeat records the file's location and a content fingerprint together with the facts you type. The file itself stays where it is, so keep it in place.

## Add an evidence record

Record the invoice file and its details:

```bash
aeat app ledger evidence add ./invoices/supplier-march.pdf --supplier "Papelería Sol SL" --invoice-number "2026-0142" --invoice-date 2026-03-10 --taxable-base 100.00 --iva-rate 21 --iva-amount 21.00 --notes "Office supplies, March"
```

The file path is the only required part; every metadata flag is optional. `--iva-rate 21` means 21 %. Add what you know now; update the rest later.

The command prints the evidence ID. Note the full ID down - later commands need it.

## Link an evidence record to a transaction

Attach the evidence record to the transaction it supports:

```bash
aeat app ledger attach --id <transaction-id> --purchase-invoice-evidence-id <evidence-id>
```

A transaction carries at most one purchase-invoice evidence record. The command refuses a second one, and refuses re-attaching the same one.

Generic file attachments are separate. Use `--attachment-id` (repeatable) to attach stored files to a transaction without the purchase-invoice role:

```bash
aeat app ledger attach --id <transaction-id> --attachment-id <file-id>
```

## Link an external document instead

When the document lives elsewhere - in Google Drive, in Gmail, or at a URL - record a document link instead:

```bash
aeat app ledger doclink --id <transaction-id> --source GOOGLE_DRIVE --reference <drive-file-id> --note "Supplier invoice"
```

Accepted sources are `GMAIL`, `GOOGLE_DRIVE`, and `URL`.

The link is saved with the transaction as a reference only. aeat never accesses or downloads the file.

## List, view, update, and remove evidence records

List every stored evidence record:

```bash
aeat app ledger evidence list
```

View one evidence record in full:

```bash
aeat app ledger evidence view <evidence-id>
```

Update details on an existing evidence record - the same optional flags as `add`:

```bash
aeat app ledger evidence update <evidence-id> --supplier "Papelería Sol SL"
```

Remove an evidence record you no longer need:

```bash
aeat app ledger evidence remove <evidence-id> --yes
```

Removing applies to evidence records, not transactions. To fix a transaction row itself, see [Correct mistakes in your ledger](correct-ledger-entries.md).

## After you correct a row

If you merge or split transactions, check the new rows and re-attach evidence where needed. [Correct mistakes in your ledger](correct-ledger-entries.md) covers row changes.

## Where evidence shows up

Ledger exports include the evidence link with each transaction. Ledger-derived calculations carry the evidence trail through to filing artifacts.

## Where to get help

- If a command fails or refuses, see [Troubleshooting](troubleshooting.md).
- If a term is unfamiliar, see the {doc}`Glossary </_generated/glossary>`.
- Before sharing command output with anyone, strip tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Work with transactions](import-bank-statements.md) - bring more transactions into the ledger.
- [Correct mistakes in your ledger](correct-ledger-entries.md) - fix mistakes in transaction rows.
- [Classify transactions](classify-transactions.md) - assign tax categories to your transactions.
- [CLI reference](../cli/index.rst) - the full command surface.
