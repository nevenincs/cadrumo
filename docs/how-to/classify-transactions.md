# Classify transactions

Use this guide after transactions are in the active profile's ledger. Imported
rows have dates and amounts, but they do not yet say how the tax calculation
should treat them.

Classifying a transaction only changes the record on your computer — nothing is sent to AEAT.

## Review the row first

Find the transaction id:

```bash
aeat app ledger list --filter classification=NOT_YET_PROCESSED
```

Inspect the row:

```bash
aeat app ledger view <transaction-id>
```

Use the description, amount, counterparty, source document, and business context
to decide how to classify the row.

## Choose the classification

Use one of the ledger classification states that command help accepts:

- `BUSINESS` for a fully business-related transaction
- `PERSONAL` for a personal transaction that should not feed tax calculations
- `MIXED` for a transaction that is partly business and partly personal

Use only these three values — others are set automatically by aeat.

## Pick a category for expenses

List accepted category ids:

```bash
aeat app ledger categories
```

Expense rows normally need a category id before a modelo can calculate from
them:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --category-id <category-id>
```

For money you received (income), aeat does not usually need a category — it calculates income totals automatically.

Use `OUTGOING` plus an expense category for supplier purchases and other
deductible expenses. Use `INCOMING` for issued invoices, client payments, or
services rendered to customers. If you also track invoice records separately,
use `aeat app ledger invoice` with `--kind received` for supplier invoices and
`--kind issued` for customer invoices.

## Add tax fields when needed

If a row needs regulated tax fields, add only the fields that apply:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --category-id <category-id> --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
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

## Classify mixed-use transactions

Use `MIXED` with a business percentage from `0` to `1`:

```bash
aeat app ledger classify <transaction-id> --classification MIXED --business-pct 0.5 --category-id <category-id>
```

You can also record allocation through the allocation command:

```bash
aeat app ledger allocate <transaction-id> --business-pct 0.5 --category-id <category-id>
```

Leave `--usage-ratio-id` out unless you have already set up a saved proportion
for this type of expense — most users do not need it. Use
`--prorrata-reference` only if your IVA return uses the prorrata rule (regla de
prorrata) — for example, if you also make VAT-exempt sales.

For shared expenses, first check which category ratios are supported:

```bash
aeat app ledger ratios eligible
aeat app ledger ratios list
```

Set or replace a category-level business-use ratio only when the category
supports it:

```bash
aeat app ledger ratios set <category-id> 0.5
aeat app ledger ratios validate
```

Remove a category ratio you no longer want with
`aeat app ledger ratios unset <category-id>`.

For home-office expenses, you normally either classify the row as `MIXED` with
an explicit `--business-pct`, or use a supported category ratio when your
profile has one. If you have linked and applied Modelo 036 censo facts with
valid home-office area data, `aeat` can seed censo-derived home-office ratios
for relevant categories. See
[Link Modelo 036 census information](censo-update.md) before relying on that
ratio.

## Classify many rows from CSV

For bulk review, `classify --from-csv` reads a CSV with columns
`transaction_id`, `classification`, and optionally `category_id`:

```bash
aeat app ledger classify --from-csv ./classifications.csv
```

The CSV path is the implemented batch-editing workflow for classifications.
Use it when filtered review shows many rows that can be classified safely from
their descriptions, counterparties, and source documents.

Recommended workflow:

1. Select rows with `ledger list`:

   ```bash
   aeat app ledger list --filter period=1T --filter year=2026 --filter classification=NOT_YET_PROCESSED
   ```

2. Export the period as a review snapshot:

   ```bash
   aeat app ledger export --output ./ledger-2026-q1.csv --year 2026 --period 1T
   ```

3. Prepare a narrow CSV containing only the rows you mean to change:

   ```text
   transaction_id,classification,category_id
   <business-expense-id>,BUSINESS,<category-id>
   <private-row-id>,PERSONAL,
   ```

4. Apply and review:

   ```bash
   aeat app ledger classify --from-csv ./classifications.csv
   aeat app ledger list --filter period=1T --filter year=2026
   aeat app ledger preflight --year 2026 --period 1T
   ```

Keep a copy of the file — it gives you a record of how you classified that
period if you are later asked to justify your return. This path does not batch-update amounts,
descriptions, IVA values, notes, attachments, or split/merge state; use the
transaction workflow for those row-level edits.

## Apply stored rules automatically

Rules automatically classify transactions whose description contains a word or
phrase you specify. Matching ignores uppercase and lowercase differences:

```bash
aeat app ledger rule add --description-pattern "software" --classification BUSINESS --category-id <category-id>
aeat app ledger rule list
aeat app ledger rule apply --dry-run
aeat app ledger rule apply
```

Run `--dry-run` first. Add `--reaffirm` only if you want the rule to overwrite
classifications you already set by hand.

## Use an LLM suggestion

aeat can use an AI assistant to suggest how to classify each transaction. The
suggestion is a starting point — you must confirm or correct it. It does not
fill in tax amounts such as taxable base, IVA rate, or IRPF category.

Use [Classify transactions with an LLM](classify-with-llm.md) for the full
provider, preview, apply, and override flow.

## Confirm readiness

Run preflight after classification:

```bash
aeat app ledger preflight --year 2026 --period 1T
aeat app ledger status --year 2026 --period 1T
```

Preflight names rows that still need category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference.

## Correct a classification

Re-run `classify` on the same transaction id:

```bash
aeat app ledger classify <transaction-id> --classification PERSONAL
```

A manual decision replaces the previous classification. Inspect the row again
with `ledger view` before calculating.

## Next steps

- [Work with Transactions](import-bank-statements.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [How your records become tax figures](../explanation/from-records-to-figures.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)

