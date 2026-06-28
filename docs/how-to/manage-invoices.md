# Manage business invoices

Record the invoices your business issues and receives — the money a customer
owes you and the money you owe a supplier. This guide covers both kinds and
shows which records feed your tax calculations.

A business invoice is not the same as a purchase receipt you attach as evidence.
Receipts support a deductible expense on a ledger transaction (see
[Attach invoices and receipts](ledger-evidence.md)). Business invoices recorded
here are the commercial documents themselves: an *issued* invoice (you billed a
customer) or a *received* invoice (a supplier billed you).

## Before you start

You need:

- An active taxpayer profile. Every command below works on the active profile;
  if none is set, the command refuses. See
  [Set up your taxpayer profile](profile-setup.md).
- A master-key passphrase. The tool prompts for it the first time it opens your
  encrypted storage in a session; for a non-interactive shell, set
  `AEAT_SECRET_PASSPHRASE`.

The CLI emits its help and messages in Spanish; the English text on this page
describes what each step does.

## Two ways to hold an invoice

`aeat` keeps invoices in two separate places, for two different jobs.

- **The invoice record** (`aeat app ledger invoice ...`) is your bookkeeping
  ledger of who owes you and whom you owe. Use it to record, list, and edit
  invoices. These records are for tracking; on their own they do **not** feed a
  modelo calculation.
- **The reconciliation catalogue** (`aeat app ledger invoice catalogue ...`) is
  the linkable copy. A catalogue invoice can be matched to a bank transaction
  and is the copy a calculation reads — for example, the Modelo 349
  recapitulative declaration of intra-community operations.

Record everyday invoices with `invoice add`. When an invoice must drive a
calculation or be reconciled against a payment, also create it in the catalogue
with `invoice catalogue create`.

Every command takes `--kind issued` or `--kind received`. *Issued* means a
customer owes you (a collectible invoice); *received* means you owe a supplier
(a payable invoice).

## Record an issued invoice

Record an invoice you sent to a customer:

```bash
aeat app ledger invoice add --kind issued \
  --counterparty-nif B12345678 --counterparty-name "Cliente SL" \
  --invoice-number FAC-2026-001 --invoice-date 2026-02-15 \
  --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --total-amount 1210
```

The command returns the new `invoice_id`, the resolved `source_kind`
(`collectible_invoice`), and the values you entered. Record the short
`invoice_id`; you address the invoice by it (or by an unambiguous prefix).

## Record a received invoice

Record an invoice a supplier sent you:

```bash
aeat app ledger invoice add --kind received \
  --counterparty-nif A87654321 --counterparty-name "Proveedor SA" \
  --invoice-number PROV-99 --invoice-date 2026-02-20 \
  --taxable-base 500 --iva-rate 0.21 --iva-amount 105 --total-amount 605
```

The `source_kind` resolves to `payable_invoice`.

## List, view, update, and remove

List both kinds, or filter to one:

```bash
aeat app ledger invoice list
aeat app ledger invoice list --kind issued
```

View one invoice by id or unambiguous prefix (the kind is required):

```bash
aeat app ledger invoice view 521e --kind issued
```

Update editable fields — for example, add a note:

```bash
aeat app ledger invoice update 521e --kind issued --notes "paid late"
```

Remove an invoice. The command asks for `--yes` to confirm:

```bash
aeat app ledger invoice remove 521e --kind issued --yes
```

## Record an intra-community invoice

A supply to, or acquisition from, a VAT-registered business in another EU
country is an intra-community operation. Record it on the issued or received
invoice with the counterparty's country and EU VAT id, plus the Modelo 349
operation type:

```bash
aeat app ledger invoice add --kind issued \
  --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" \
  --invoice-number EU-001 --invoice-date 2026-02-10 \
  --taxable-base 2000 --iva-rate 0 --iva-amount 0 --total-amount 2000 \
  --country-code DE --eu-iva-id DE345678901 --operation-type E
```

`--operation-type` takes one M349 code: `E` goods supply, `S` services
supplied, `T` triangular, `R` rectification, `A` goods acquisition, `I`
services acquired, `M` miscellaneous.

## Feed a calculation from the catalogue

To make an invoice reach a modelo calculation, create it in the catalogue. The
catalogue copy is the one a calculation reads and the one you can link to a bank
transaction:

```bash
aeat app ledger invoice catalogue create --kind issued \
  --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" \
  --invoice-number EU-CAT-001 --invoice-date 2026-02-10 \
  --taxable-base 2000 --iva-rate 0 --country-code DE --operation-type E
```

For an intra-community operation, pass `--operation-type` so the catalogue
stamps the classification the Modelo 349 calculation reads. The catalogue feeds
the three operation types the recapitulative calculation can represent today —
`E` (goods supply), `A` (goods acquisition), and `T` (triangular). The service,
rectification, and miscellany codes are refused here rather than silently
dropped:

```text
Invalid value: --operation-type S cannot feed Modelo 349 from the catalogue
yet; supported: E, A, T.
```

List the catalogue copies:

```bash
aeat app ledger invoice catalogue list
```

Inspect one catalogue invoice to confirm its id and its linked transactions.
Pass the full id or an unambiguous prefix:

```bash
aeat app ledger invoice catalogue view <catalogue-invoice-id>
```

Link a catalogue invoice to the bank transaction that paid or collected it:

```bash
aeat app ledger link <transaction-id> --invoice-id <catalogue-invoice-id>
```

Remove a catalogue invoice you created by mistake. Confirm with `--yes`:

```bash
aeat app ledger invoice catalogue remove <catalogue-invoice-id> --yes
```

Unlink the invoice first if it is still linked to a transaction. A removal of a
still-linked invoice is refused, so the bank transaction never ends up citing an
invoice that no longer exists.

## See the invoice in Modelo 349

After cataloguing intra-community invoices for a period, create and calculate
the recapitulative declaration. Use the month or quarter the invoices were
issued in:

```bash
aeat app modelo work create --modelo 349 --year 2026 --period 02
aeat app modelo work calculate --modelo 349 --year 2026 --period 02
```

The declaration totals report one operator and the summed base for the period.
An invoice is counted only in the period its invoice date falls in — Modelo 349
reads invoices strictly by date, with no carry-forward from earlier periods.

## Which modelos read your invoices

Catalogue invoices feed **Modelo 349** — the recapitulative declaration of
intra-community operations — through the operation type you stamp on them
(`E`/`A`/`T`). This is the modelo your issued and received invoices drive
directly.

Your **IVA returns do not read these invoice records**. Modelo 303 (quarterly
IVA) and Modelo 390 (annual IVA summary) are computed from your classified
ledger transactions, not from the invoice catalogue. Record the income and
expense in the ledger and classify it (see
[Classify transactions](classify-transactions.md)); the IVA returns read the
ledger. Recording an invoice here does not add it to a Modelo 303.

Cross-border B2C sales under the One-Stop-Shop scheme (Modelo 369) are a
separate flow not yet reachable from `invoice catalogue create`; record those
through the OSS-specific workflow.

## Where to go next

- [Attach invoices and receipts](ledger-evidence.md)
- [Work with transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [CLI reference](../cli/index.rst)
