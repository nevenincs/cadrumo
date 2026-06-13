# Work through the review queue

The review queue is one list of everything that still wants your attention
before a filing: transactions without a classification, invoice records that
are unmatched or disputed, and verification findings on modelo drafts. Each
row names the exact command that resolves it, so the queue is a to-do list
you can work through top to bottom.

The queue is read-only. Listing it changes nothing; items clear when you fix
the underlying record with the command the row names.

## List what is pending

Show every pending item for the active profile:

```bash
aeat app review queue
```

Each row shows the item id, its kind, the affected record, the period, a
severity (`critical`, `high`, `normal`, or `info`), and a final column with
the command to run next for that item.

## Narrow the list

Filter by kind, modelo, or state:

```bash
aeat app review queue --kind ledger_transaction
aeat app review queue --kind modelo_finding --modelo 303
aeat app review queue --state all
```

Accepted `--kind` tokens are `ledger_transaction`, `purchase_invoice_evidence`,
`payable_invoice`, `collectible_invoice`, and `modelo_finding`. The default
state is `pending`; `--state all` widens the filter. An unknown kind is
refused with the accepted set named.

## Inspect one item

Show one item in full, including the suggested next command:

```bash
aeat app review view <item-id>
```

## See the legal grounding

Modelo findings are grounded in registry rules. Add `--explain` to show the
legal references behind each finding in the text output:

```bash
aeat app review queue --kind modelo_finding --explain
aeat app review view <item-id> --explain
```

The JSON output always carries the `legal_refs`; `--explain` adds them to the
text table. Transaction and invoice items carry no legal references — their
obligation comes from your own records, not from a registry rule.

## Where items come from and what clears them

- **Transactions** appear while a row has no final classification. Classify
  the row and it leaves the queue — see
  [Classify transactions](classify-transactions.md). Rows that are fully
  classified or skipped by rule do not appear.
- **Invoices** appear while an invoice record is unmatched, disputed, or
  pending. Link the invoice to its transaction or update its state — see
  [Attach invoices and receipts](ledger-evidence.md).
- **Modelo findings** appear while a draft has verification findings or is
  not ready. Fix the reported values and verify again — see
  [Verify a filing](verification-reports.md).

`aeat app review queue` is profile-wide. For inspecting individual ledger
rows in detail, use `aeat app ledger review` instead — see
[Work with transactions](import-bank-statements.md).

## Next steps

- [Classify transactions](classify-transactions.md) — clear transaction
  items.
- [Attach invoices and receipts](ledger-evidence.md) — clear invoice items.
- [Verify a filing](verification-reports.md) — clear modelo findings.
- [Correct mistakes in your ledger](correct-ledger-entries.md) — fix the
  underlying rows.
- [CLI reference](../cli/index.rst) — full option reference.
