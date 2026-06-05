# Classify transactions

Use this guide after transactions are in the active profile's ledger. Imported
rows have dates and amounts, but they do not yet say how the tax calculation
should treat them.

Classification is local. It changes the saved ledger row for the active profile
and does not contact AEAT.

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

Other internal states exist for processing and validation, but these three are
the normal operator choices.

## Pick a category for expenses

List accepted category ids:

```bash
aeat app ledger categories
```

Expense rows normally need a category id before a modelo can calculate from
them:

```bash
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id>
```

Income rows usually do not need `--category-id`; `aeat` can use transaction
direction and ledger income aggregation.

## Add tax fields when needed

If a row needs regulated tax fields, add only the fields that apply:

```bash
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id> --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00
```

Common fields include taxable base, IVA rate, IVA amount, IVA category, IRPF
category, and counterparty EU member state for intracommunity IVA cases. Use
`aeat app ledger classify --help` for the exact current option list.

## Classify mixed-use transactions

Use `MIXED` with a business percentage from `0` to `1`:

```bash
aeat app ledger classify --id <transaction-id> --classification MIXED --business-pct 0.5 --category-id <category-id>
```

You can also record allocation through the allocation command:

```bash
aeat app ledger allocate --id <transaction-id> --business-pct 0.5 --category-id <category-id>
```

`0` means personal, `1` means fully business, and a value between them means
mixed use. Use `--usage-ratio-id` only when you have already created a reusable
usage ratio for the profile. Use `--prorrata-reference` only for IVA workflows
that need a prorrata reference.

## Classify many rows from CSV

For bulk review, `classify --from-csv` reads a CSV with columns
`transaction_id`, `classification`, and optionally `category_id`:

```bash
aeat app ledger classify --from-csv ./classifications.csv
```

Keep bulk files as review artifacts. They are useful when you later need to
explain how a period was classified.

## Use an LLM suggestion

An LLM can suggest business/personal/mixed classification and, when possible,
an expense category. It does not set regulated tax figures such as taxable base,
IVA rate, IVA amount, IVA category, or IRPF category.

Use [Classify a transaction with an LLM](classify-with-llm.md) for the full
provider, preview, apply, and override flow.

## Confirm readiness

Run preflight after classification:

```bash
aeat app ledger preflight --period 2026Q1
aeat app ledger status --period 2026Q1
```

Preflight names rows that still need category, taxable base, IVA amount, IVA
rate, currency, or proportionality reference.

## Correct a classification

Re-run `classify` on the same transaction id:

```bash
aeat app ledger classify --id <transaction-id> --classification PERSONAL
```

A manual decision replaces the previous classification. Inspect the row again
with `ledger view` before calculating.

## Next steps

- [Work with transaction data](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
