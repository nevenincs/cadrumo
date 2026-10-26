# Manage business invoices

Record the invoices your business issues and receives: the money a customer
owes you and the money you owe a supplier. This guide covers both kinds and
shows which records feed your tax calculations.

A business invoice is not the same as a purchase receipt you attach as a supporting document.
Receipts support a deductible expense on a transaction in your records (see
[Attach invoices and receipts to transactions](ledger-evidence.md)). Business invoices recorded
here are the commercial documents themselves: an *issued* invoice (you billed a
customer) or a *received* invoice (a supplier billed you).

## Before you start

You need:

- An active taxpayer profile. Every command on this page works on the active profile;
  if none is set, the command refuses. See
  [Set up your taxpayer profile](profile-setup.md).
- Your passphrase. The tool prompts for it the first time it opens your
  encrypted storage in a session.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you
[choose another language](profile-setup.md#choose-the-output-language).

## One invoice catalogue

Cadrumo keeps business invoices in one catalogue (`aeat app ledger invoice
...`): a record of who owes you and whom you owe. Use it to record, list, and
edit invoices.

Every invoice you record is linkable and calculable. Match it to a bank
transaction with `aeat app ledger link`, and a calculation reads it directly, for example the Modelo 349 recapitulative declaration of intra-community
operations.

Record every invoice with `invoice add`. There is no second copy to create.

`invoice add` requires `--kind issued` or `--kind received`, and
`invoice list` accepts it as a filter. *Issued* means a customer owes you;
*received* means you owe a supplier. `invoice view`, `update`, and `remove`
take only the invoice id. `invoice add` also requires `--country-code`, the
counterparty's two-letter country code.

## Record an issued invoice

Record an invoice you sent to a customer. The command returns the new
`invoice_id`, the computed totals, and the values you entered:

```{cli-sequence} invoices-record-issued
:verify: Confirm the issued invoice was stored with its computed total.
```

Record the `invoice_id`; you address the invoice by it (or by an
unambiguous prefix).

## Record a received invoice

Record an invoice a supplier sent you. Its `kind` reads `received`:

```{cli-sequence} invoices-record-received
:verify: Confirm the received invoice was stored with its computed total.
```

## List, view, update, and remove

List both kinds or filter to one, add a note to a stored invoice, then remove it.
The view of one invoice takes its id (or an unambiguous prefix):

```{cli-sequence} invoices-list-update-remove
:verify: Confirm the note was added and the invoice then removed.
```

## Record an intra-community invoice

A supply to, or acquisition from, a VAT-registered business in another EU
country is an intra-community operation. Record it on the issued or received
invoice with the counterparty's country and EU VAT id, plus the Modelo 349
operation type:

```{cli-sequence} invoices-record-intracommunity
:verify: Confirm the operation type and country were stored on the issued invoice.
```

`--operation-type` takes one M349 operation key: `E` supplies of goods, `M`
supplies after an exempt import, `H` the same via a fiscal representative,
`A` acquisitions of goods, `T` triangular supplies, `S` services supplied,
`I` services acquired, and the call-off-stock keys `R` (transfers), `D`
(returns), and `C` (substitutions).

`invoice update` corrects the note, counterparty name and country, operation
type and date, VAT category, withholding, invoice class, series, and the
rectified invoice number. To correct the invoice number, date, tax id,
currency, or totals, remove the invoice and record it again.

## Feed a calculation from the catalogue

Every invoice in the catalogue reaches a modelo calculation and can be linked
to a bank transaction. The sequence records an intra-community supply, lists
and inspects the catalogue, then creates and calculates the Modelo 349
recapitulative declaration for the period the invoice falls in:

```{cli-sequence} invoices-catalogue-and-349
:verify: Confirm the catalogued invoice reaches the Modelo 349 calculation.
```

For an intra-community operation, pass `--operation-type` so the invoice
carries the classification the Modelo 349 calculation reads. Use `E`, `H`, `M`,
`S`, `T`, `R`, `D`, or `C` for issued catalogue invoices. Use `A`, `I`, or `T`
for received catalogue invoices. In Modelo 349, `R` is the call-off-stock
transfer key; rectification rows use separate rectified-period and base fields.

An invoice is counted in the period of the date you record with
`--operation-date`, so record the devengo date that LIVA art. 75 sets. For an
intra-community supply of goods, that is the 15th of the month after the
transport starts, or the invoice date if it is earlier (art. 75.Uno.8.º).
Without `--operation-date`, the invoice date stands in for it. Modelo 349
reads invoices strictly by that date, with no carry-forward from earlier
periods.

## Link a catalogue invoice to a transaction

Link a catalogue invoice to the bank transaction that paid or collected it. The
example starts with one bank transaction and one issued invoice, links them,
and confirms the link on the invoice:

```{cli-sequence} invoices-link-catalogue
:verify: Confirm the catalogue invoice records the linked transaction.
```

Remove a catalogue invoice you created by mistake, confirming with `--yes`.
If the invoice is still linked to a transaction, the removal is refused, so
the bank transaction never ends up citing an invoice that no longer exists.
`aeat` has no command that unlinks an invoice. Removing the linked transaction
releases the link (see [Correct mistakes in your records](correct-ledger-entries.md)).
The example removes an invoice that has no link:

```{cli-sequence} invoices-catalogue-remove
:verify: Confirm the catalogue invoice was removed.
```

## Which modelos read your invoices

Catalogue invoices feed **Modelo 349** (the recapitulative declaration of
intra-community operations) through the operation type you stamp on them
when you create them. This is the modelo your issued and received invoices
drive directly. Modelo 100 calculations also read the invoice linked to an
income or expense transaction, for example the withholding declared on it.

Modelo 303 (quarterly VAT) and Modelo 390 (annual VAT summary) take their
amounts from the transactions you have classified in your records, not from the
invoice catalogue. They do check the catalogue: if an invoice's VAT for the
period exceeds what your records carry, the calculation refuses until you record and classify the matching
transactions (see [Classify transactions](classify-transactions.md)).
Recording an invoice here does not add it to a Modelo 303.

Cross-border B2C sales under the One-Stop-Shop scheme (Modelo 369) are a
separate flow not yet reachable from `invoice add`; record those
through the OSS-specific workflow.

## Where to go next

- [Attach invoices and receipts to transactions](ledger-evidence.md)
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Prepare a Modelo 303 VAT filing](modelo-303.md)
- [CLI reference](../cli/index.rst)
