# Attach invoices and receipts to ledger transactions

Store an evidence record for each invoice or receipt and link it to the transaction it supports. Checks, exports, and year-end reviews can then point at the document behind every number. Everything happens on your computer - nothing is uploaded or sent anywhere.

## Before you start

You need:

- Transactions in your ledger. If your ledger is empty, see [Work with transactions](import-bank-statements.md) first.
- The invoice or receipt as a PDF or image file. aeat copies the file's bytes into encrypted storage together with the facts you type, plus a content fingerprint and the original location as provenance. Your original file is never needed again after `add`.

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
aeat app ledger attach <transaction-id> --purchase-invoice-evidence-id <evidence-id>
```

A transaction carries at most one purchase-invoice evidence record. The command refuses a second one, and refuses re-attaching the same one.

Generic file attachments are separate. Use `--attachment-id` (repeatable) to attach stored files to a transaction without the purchase-invoice role:

```bash
aeat app ledger attach <transaction-id> --attachment-id <file-id>
```

## Pull a document from Google Drive instead

When the document lives in Google Drive, pull it straight into encrypted evidence storage:

```bash
aeat app ledger doclink <transaction-id> --source GOOGLE_DRIVE --reference <drive-file-id> --note "Supplier invoice"
```

The command downloads the Drive file, stores its bytes encrypted with the transaction, and keeps the original link as provenance. Evidence always carries the document itself, never a bare link: Gmail links, arbitrary URLs, and Drive files outside the granted scope are refused. For a refused source, download the document yourself and attach it with `aeat app ledger evidence add` or `aeat app ledger attach --attachment-id`.

## Track invoice records

An invoice record tracks the invoice itself — who owes whom, for what amount
— independently of any bank movement or stored document. Use it when you
issue or receive an invoice that is not settled yet, or when you want the
invoice facts queryable on their own.

Register an invoice:

```bash
aeat app ledger invoice add --kind received --counterparty-nif B12345678 --invoice-number "2026-0142" --invoice-date 2026-03-10 --taxable-base 100.00 --iva-rate 21 --iva-amount 21.00 --total-amount 121.00
```

`--kind` is required on every invoice command: `issued` means a customer owes
you (an invoice you issued); `received` means you owe a supplier (an invoice
you received). The counterparty identifier, invoice number, and invoice date
(YYYY-MM-DD) are required; the amount fields are optional.

For an intra-community EU operation, add the counterparty's country and EU
IVA identifier, and the operation type used by Modelo 349:

```bash
aeat app ledger invoice add --kind issued --counterparty-nif X1234567X --invoice-number "2026-0007" --invoice-date 2026-03-12 --country-code DE --eu-iva-id DE345678901 --operation-type S
```

Work with stored invoice records:

```bash
aeat app ledger invoice list
aeat app ledger invoice view <invoice-id> --kind received
aeat app ledger invoice update <invoice-id> --kind received --total-amount 121.00
aeat app ledger invoice remove <invoice-id> --kind received --yes
```

`list` shows both kinds unless you filter with `--kind`. `view`, `update`,
and `remove` need `--kind` to address the record; `remove` refuses without
`--yes`. An unambiguous prefix of the invoice id is enough.

Link an invoice record to the bank movement that settles it:

```bash
aeat app ledger link <transaction-id> --invoice-id <invoice-id>
```

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
