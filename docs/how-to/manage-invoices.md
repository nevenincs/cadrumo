# Manage business invoices

Record the invoices your business issues and receives: the money a customer
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
  encrypted storage in a session.

The `aeat` command-line interface (CLI) emits its help and messages in Spanish; the English text on this page
describes what each step does.

## Two ways to hold an invoice

Cadrumo keeps invoices in two separate places, for two different jobs.

- **The invoice record** (`aeat app ledger invoice ...`) is your bookkeeping
  ledger of who owes you and whom you owe. Use it to record, list, and edit
  invoices. These records are for tracking; on their own they do **not** feed a
  modelo calculation.
- **The reconciliation catalogue** (`aeat app ledger invoice catalogue ...`) is
  the linkable copy. A catalogue invoice can be matched to a bank transaction
  and is the copy a calculation reads, for example the Modelo 349
  recapitulative declaration of intra-community operations.

Record everyday invoices with `invoice add`. When an invoice must drive a
calculation or be reconciled against a payment, also create it in the catalogue
with `invoice catalogue create`.

Every command takes `--kind issued` or `--kind received`. *Issued* means a
customer owes you (a collectible invoice); *received* means you owe a supplier
(a payable invoice).

## Record an issued invoice

Record an invoice you sent to a customer. The command returns the new
`invoice_id`, the resolved `source_kind` (`collectible_invoice`), and the values
you entered:

```{cli-sequence} invoices-record-issued
:verify: Confirm the issued invoice was stored as a collectible invoice.
@step Record an invoice you sent to a customer.
aeat --format json app ledger invoice add --kind issued --counterparty-nif B12345678 --counterparty-name "Cliente SL" --invoice-number FAC-2026-001 --invoice-date 2026-02-15 --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --total-amount 1210
@capture invoice_id result.invoice_id
@step Confirm it resolved to a collectible invoice.
@result aeat --format json app ledger invoice view {invoice_id} --kind issued
@expect result.source_kind == "collectible_invoice"
@expect result.total_amount == "1210"
```

Record the short `invoice_id`; you address the invoice by it (or by an
unambiguous prefix).

## Record a received invoice

Record an invoice a supplier sent you. The `source_kind` resolves to
`payable_invoice`:

```{cli-sequence} invoices-record-received
:verify: Confirm the received invoice was stored as a payable invoice.
@step Record an invoice a supplier sent you.
aeat --format json app ledger invoice add --kind received --counterparty-nif A87654321 --counterparty-name "Proveedor SA" --invoice-number PROV-99 --invoice-date 2026-02-20 --taxable-base 500 --iva-rate 0.21 --iva-amount 105 --total-amount 605
@capture invoice_id result.invoice_id
@step Confirm it resolved to a payable invoice.
@result aeat --format json app ledger invoice view {invoice_id} --kind received
@expect result.source_kind == "payable_invoice"
```

## List, view, update, and remove

List both kinds or filter to one, add a note to a stored invoice, then remove it.
The view of one invoice takes its id (or an unambiguous prefix) and the kind:

```{cli-sequence} invoices-list-update-remove
:verify: Confirm the note was added and the invoice then removed.
@step Record an issued invoice to manage.
@setup aeat --format json app ledger invoice add --kind issued --counterparty-nif B12345678 --counterparty-name "Cliente SL" --invoice-number FAC-2026-050 --invoice-date 2026-02-15 --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --total-amount 1210
@capture invoice_id result.invoice_id
@step List every invoice, both kinds.
aeat app ledger invoice list
@step Filter the list to issued invoices only.
aeat app ledger invoice list --kind issued
@step Add a note to the invoice.
aeat app ledger invoice update {invoice_id} --kind issued --notes "paid late"
@step Remove the invoice, confirming with --yes.
@result aeat --format json app ledger invoice remove {invoice_id} --kind issued --yes
@expect result.notes == "paid late"
@expect exit_code == 0
```

## Record an intra-community invoice

A supply to, or acquisition from, a VAT-registered business in another EU
country is an intra-community operation. Record it on the issued or received
invoice with the counterparty's country and EU VAT id, plus the Modelo 349
operation type:

```{cli-sequence} invoices-record-intracommunity
:verify: Confirm the operation type and country were stored on the issued invoice.
@step Record a supply to a VAT-registered EU customer with its M349 operation type.
aeat --format json app ledger invoice add --kind issued --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" --invoice-number EU-001 --invoice-date 2026-02-10 --taxable-base 2000 --iva-rate 0 --iva-amount 0 --total-amount 2000 --country-code DE --eu-iva-id DE345678901 --operation-type E
@capture invoice_id result.invoice_id
@step Confirm the operation type and country were stored.
@result aeat --format json app ledger invoice view {invoice_id} --kind issued
@expect result.operation_type == "E"
@expect result.country_code == "DE"
```

`--operation-type` takes one M349 operation key: `E` supplies of goods, `M`
supplies after an exempt import, `H` the same via a fiscal representative,
`A` acquisitions of goods, `T` triangular supplies, `S` services supplied,
`I` services acquired, and the call-off-stock keys `R` (transfers), `D`
(returns), and `C` (substitutions).

## Feed a calculation from the catalogue

To make an invoice reach a modelo calculation, create it in the catalogue. The
catalogue copy is the one a calculation reads and the one you can link to a bank
transaction. The sequence catalogues an intra-community supply, lists and
inspects the catalogue, then creates and calculates the Modelo 349
recapitulative declaration for the period the invoice falls in:

```{cli-sequence} invoices-catalogue-and-349
:verify: Confirm the catalogued invoice reaches the Modelo 349 calculation.
@step Catalogue an intra-community supply so a calculation can read it.
aeat --format json app ledger invoice catalogue create --kind issued --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" --invoice-number EU-CAT-001 --invoice-date 2026-02-10 --taxable-base 2000 --iva-rate 0 --country-code DE --operation-type E
@capture invoice_id result.invoice_id
@expect result.operation_type == "E"
@step List the catalogue copies.
aeat app ledger invoice catalogue list
@step Inspect one catalogue invoice to confirm its id.
aeat --format json app ledger invoice catalogue view {invoice_id}
@expect result.base_total == "2000.00"
@step Create the Modelo 349 work unit for the period the invoice falls in.
aeat --format json app modelo work create --modelo 349 --year 2026 --period 02
@capture work_unit_id result.work_unit_id
@step Calculate the recapitulative declaration.
@result aeat --format json app modelo work calculate {work_unit_id}
@expect result.operation == "modelo.work.calculate"
@expect exit_code == 0
```

For an intra-community operation, pass `--operation-type` so the catalogue
stamps the classification the Modelo 349 calculation reads. Use `E`, `H`, `M`,
`S`, `T`, `R`, `D`, or `C` for issued catalogue invoices. Use `A`, `I`, or `T`
for received catalogue invoices. In Modelo 349, `R` is the call-off-stock
transfer key; rectification rows use separate rectified-period and base fields.

An invoice is counted only in the period its invoice date falls in. Modelo 349
reads invoices strictly by date, with no carry-forward from earlier periods.

## Link a catalogue invoice to a transaction

Link a catalogue invoice to the bank transaction that paid or collected it. The
sequence records a transaction, catalogues an invoice, links them, and confirms
the link on the catalogue copy:

```{cli-sequence} invoices-link-catalogue
:verify: Confirm the catalogue invoice records the linked transaction.
@step Record the bank transaction that collected the invoice.
@setup aeat --format json app ledger add --date 2026-02-12 --amount 2000 --direction INCOMING --description "Cobro cliente DE" --idempotency-key invoices-link
@capture transaction_id result.transaction_id
@step Catalogue the issued invoice.
@setup aeat --format json app ledger invoice catalogue create --kind issued --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" --invoice-number EU-CAT-050 --invoice-date 2026-02-10 --taxable-base 2000 --iva-rate 0 --country-code DE --operation-type E
@capture invoice_id result.invoice_id
@step Link the catalogue invoice to the transaction that collected it.
aeat app ledger link {transaction_id} --invoice-id {invoice_id}
@step Confirm the catalogue invoice now records the linked transaction.
@result aeat --format json app ledger invoice catalogue view {invoice_id}
@expect result.operation_type == "E"
@expect exit_code == 0
```

Remove a catalogue invoice you created by mistake, confirming with `--yes`.
Unlink the invoice first if it is still linked to a transaction: a removal of a
still-linked invoice is refused, so the bank transaction never ends up citing an
invoice that no longer exists:

```{cli-sequence} invoices-catalogue-remove
:verify: Confirm the catalogue invoice was removed.
@step Catalogue an invoice to remove.
@setup aeat --format json app ledger invoice catalogue create --kind issued --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" --invoice-number EU-CAT-099 --invoice-date 2026-02-10 --taxable-base 2000 --iva-rate 0 --country-code DE --operation-type E
@capture invoice_id result.invoice_id
@step Remove the unlinked catalogue invoice.
@result aeat --format json app ledger invoice catalogue remove {invoice_id} --yes
@expect result.invoice_number == "EU-CAT-099"
@expect exit_code == 0
```

## Which modelos read your invoices

Catalogue invoices feed **Modelo 349** (the recapitulative declaration of
intra-community operations) through the operation type you stamp on them
when you create them. This is the modelo your issued and received invoices
drive directly.

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
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [CLI reference](../cli/index.rst)
