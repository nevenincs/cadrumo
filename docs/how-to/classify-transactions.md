# Classify transactions

This page covers the classification of ledger transactions: deciding whether a
row is business, personal, or mixed, adding the category and tax fields a
calculation needs, recording mixed-use shares, batch and rule-based
classification, and the review queue that lists everything still waiting for a
decision. Use it after transactions are in the active profile's ledger -
imported rows have dates and amounts, but they do not yet say how the tax
calculation should treat them.

Classifying a transaction changes only the record on your computer. It sends
nothing to Spain's Tax Agency (AEAT).

## Before you start

You need:

- An active taxpayer profile. Every command below works on the active profile; if none is set, the command refuses. See [Set up your taxpayer profile](profile-setup.md).
- A master-key passphrase. The tool prompts for it the first time it opens your encrypted storage in a session.
- A ledger with transactions in it. See [Import and manage transactions](import-bank-statements.md) to import a bank statement or add rows by hand.

The CLI help and error text render in Spanish, even though this guide is in English. When a step sends you to `--help`, expect Spanish option names.

## Review the row first

Find the transaction id, then inspect the row before you classify it. The
sequence imports the standard quarter and inspects the unclassified expense:

```{cli-sequence} classify-review-row
:verify: Confirm the row is still unclassified before you decide.
```

Use the description, amount, counterparty, source document, and business context
to decide how to classify the row.

## Choose the classification

Use one of the ledger classification states that command help accepts:

- `BUSINESS` for a fully business-related transaction
- `PERSONAL` for a personal transaction that should not feed tax calculations
- `MIXED` for a transaction that is partly business and partly personal

Use only these three values. Cadrumo sets the others automatically.

## Pick a category for expenses

List the accepted category ids, then classify an expense row with one. Expense
rows normally need a category id before a modelo can calculate from them:

```{cli-sequence} classify-expense-category
:verify: Confirm the expense is classified as business with a category.
```

For money you received (income), Cadrumo does not usually need a category. It
calculates income totals automatically.

Use `OUTGOING` plus an expense category for supplier purchases and other
deductible expenses. Use `INCOMING` for issued invoices, client payments, or
services rendered to customers. If you also track invoice records separately,
use `aeat app ledger invoice` with `--kind received` for supplier invoices and
`--kind issued` for customer invoices.

## Add tax fields when needed

If a row needs regulated tax fields, add only the fields that apply. The
sequence classifies the expense with its taxable base, rate, and IVA amount:

```{cli-sequence} classify-tax-fields
:verify: Confirm the taxable base and IVA fields were recorded on the row.
```

Common fields include taxable base, IVA rate, IVA amount, IVA category, IRPF
category, and counterparty EU member state for intracommunity IVA cases. Use
`aeat app ledger classify --help` for the exact current option list.

For ordinary domestic IVA, use the taxable base, rate, and amount shown by the
invoice. For example, a EUR 121.00 purchase with 21 percent IVA usually has
`--taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00`.

Most purchases at the standard 21% rate need no `--iva-category`. Add it only
for special cases: reduced rate (food, books), exempt supplies, purchases from
EU suppliers, or recargo de equivalencia. Run
`aeat app ledger classify --help` to see the accepted values.

(classify-mixed-use-transactions)=
## Classify mixed-use transactions

A mixed-use transaction is one you use partly for business and partly
personally, such as a phone bill, a car cost, or a home-office expense. Record
the business share so the calculation counts only the deductible part. The
split can come from three places, in rising order of grounding: a percentage
on a single record, a saved default ratio for a whole category, or a ratio
worked out from your registered facts (for example, the registered home-office
area against the size of your home). All three keep only the part of a cost
that genuinely belongs to the business.

A `MIXED` row needs a proportionality reference before a modelo can calculate
from it. The reference is a saved category ratio applied through
`--usage-ratio-id`. A bare `--business-pct` records a percentage but does not
make the row ready; preflight still reports `missing_proportionality_reference`
until the row carries `--usage-ratio-id`.

For one-row commands, `--usage-ratio-id` lives on the `allocate` verb (and on
`add`), not on `classify`. Its value is the spending-category id, and the same
category must already have a saved ratio. The sequence checks the eligible
categories, saves a ratio, and allocates the share on a row:

```{cli-sequence} classify-mixed-use
:verify: Confirm the mixed-use row carries the allocated business share.
```

A row's `--usage-ratio-id` must name a ratio-eligible category (the ones
`ratios eligible` lists, such as `telefonia_movil` or a home-office suministros
category), and the same category is passed as `--category-id`. The
`--business-pct` value must match the saved ratio for that category. The
classification follows the share automatically: a `0.5` allocation becomes
`MIXED`, a `1` allocation becomes `BUSINESS`, and a `0` allocation becomes
`PERSONAL`.

List or check the saved ratios at any time. The sequence saves a ratio, lists
the saved ratios, and validates them:

```{cli-sequence} classify-ratios-manage
:verify: Confirm the saved ratios validate cleanly.
```

Remove a category ratio you no longer want with
`aeat app ledger ratios unset <category-id>`.

For home-office expenses, save a ratio for the relevant home-office category
and allocate as above. Home-office ratios follow the manual or saved ratio
workflow; keep the census facts in your profile correct first - see
[Maintain Modelo 036 census facts in your profile](censo-update.md).

## Classify many rows from CSV

For bulk review, `classify --file` reads a CSV with columns
`transaction_id`, `classification`, and optional classification facts such as
`category_id`, `business_pct`, `usage_ratio_id`, taxable-base and IVA columns,
`iva_category`, and `irpf_category`. Prepare a narrow CSV holding only the rows
you mean to change, one row per transaction:

```text
transaction_id,classification,category_id,business_pct,usage_ratio_id
<business-expense-id>,BUSINESS,<category-id>,,
<mixed-expense-id>,MIXED,<category-id>,0.5,<category-id>
<private-row-id>,PERSONAL,,,
```

The sequence below imports the quarter, lists the rows still needing a decision,
exports a review snapshot to work from, applies a prepared CSV, and confirms the
result:

```{cli-sequence} classify-from-csv
:verify: Confirm the CSV batch classified the quarter's rows.
```

Use the CSV path when filtered review shows many rows you can classify safely
from their descriptions, counterparties, and source documents. Keep a copy of
the file. It gives you a record of how you classified that period if you are
later asked to justify your return. This path does not batch-update amounts,
descriptions, IVA values, notes, attachments, or split/merge state; use the
transaction workflow for those row-level edits.

## Apply stored rules automatically

Rules automatically classify transactions whose description contains a word or
phrase you specify. Matching ignores uppercase and lowercase differences. The
sequence adds a rule, lists the rules, previews the effect, then applies it:

```{cli-sequence} classify-rules
:verify: Confirm the stored rule is registered and applies cleanly.
```

Run `--dry-run` first. Add `--reaffirm` only if you want the rule to overwrite
classifications you already set by hand.

## Use an LLM suggestion

Cadrumo can use a configured language model to suggest how to classify each
transaction. The suggestion is a starting point. You must confirm or correct
it. It does not fill in tax amounts such as taxable base, IVA rate, or IRPF
category.

Use [Classify transactions with an LLM](classify-with-llm.md) for the full
provider, preview, apply, and override flow.

(see-everything-that-still-needs-a-decision)=
## See everything that still needs a decision

The review queue is one profile-wide list of everything that still wants your
attention before a filing: transactions without a classification, invoice
records that are unmatched or disputed, and verification findings on modelo
drafts. Each row names the exact command that resolves it, so the queue is a
to-do list you can work through top to bottom. The queue is read-only; items
clear when you fix the underlying record with the command the row names. The
sequence imports the quarter, then reads the queue:

```{cli-sequence} classify-review-queue
:verify: Confirm the review queue lists the pending work.
```

Each row shows the item id, its kind, the affected record, the period, a
severity (`critical`, `high`, `normal`, or `info`), and a final column with
the command to run next. Narrow the list by kind, modelo, or state:

```{cli-sequence} classify-review-queue-filter
:verify: Confirm the queue can be narrowed by kind.
```

Accepted `--kind` tokens are `ledger_transaction`, `purchase_invoice_evidence`,
`payable_invoice`, `collectible_invoice`, and `modelo_finding`. The default
state is `pending`. Inspect one item in full, including the suggested next
command, with `aeat app review view <item-id>`. Modelo findings are grounded
in registry rules; add `--explain` to show the legal references, or use the
global `--format json` flag (before the command) for a `legal_refs` field on
every row.

Transaction items clear when you classify the row (this page). Invoice items
clear when you link or update the invoice - see
[Attach invoices and receipts](ledger-evidence.md). Modelo findings clear when
you fix the reported values and verify again - see
[Verify a filing](verification-reports.md).

## Confirm readiness

Run preflight after classification. The sequence imports and classifies the
quarter, then runs preflight and reads the ledger status:

```{cli-sequence} classify-confirm-readiness
:verify: Confirm preflight reports the classified quarter's readiness.
```

Preflight names rows that still need category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference.

## Correct a classification

Re-run `classify` on the same transaction id. A manual decision replaces the
previous classification. The sequence classifies a row as business, then
corrects it to personal:

```{cli-sequence} classify-correct
:verify: Confirm the re-classification replaced the previous decision.
```

Inspect the row again with `ledger view` before calculating.

## Next steps

- [Import and manage transactions](import-bank-statements.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [How your records become tax figures](../explanation/from-records-to-figures.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
