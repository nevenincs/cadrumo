# Classify transactions with an LLM

Use this after the ledger row exists in [Work with Transactions](import-bank-statements.md).
If the provider CLI is not installed, on `PATH`, and authenticated already,
start with [Set up LLM classification providers](setup-llm-classification.md).

```bash
aeat app ledger classify --id <transaction-id> --llm claude
```

That command asks the `claude` provider for a suggestion and previews the
result. It does not save anything. Use `gemini` or `codex` instead of `claude`
when that is the provider CLI you have configured.

## What the command does

`aeat` loads one transaction from the
[active profile](profile-setup.md#what-the-active-profile-means) ledger and
sends that row to the selected local provider CLI. The provider suggests:

- a classification: `BUSINESS`, `PERSONAL`, or `MIXED`
- an expense category, when it can choose one from the allowed category list
- confidence and a short reason

The preview output includes the transaction id, provider, suggested
classification, suggested category when present, confidence, reason,
provenance, and whether the result was persisted. In preview mode, it is not
persisted.

Classification does not contact AEAT and does not submit anything. The provider
CLI may contact its own external service depending on your provider setup; see
[Set up LLM classification providers](setup-llm-classification.md) before using
real taxpayer data.

## Current limits

The LLM path is single-transaction only. It cannot be combined with
`--from-csv` or manual `--classification` flags.

An applied LLM suggestion saves only:

- `business_classification`
- optional expense `category_id`
- `classified_by=llm:<provider>`
- confidence and reason
- a local bucket event

It does not set regulated tax fields such as `taxable_base`, `iva_rate`,
`iva_amount`, `iva_category`, or `irpf_category`. Add those manually in
[Classify transactions](classify-transactions.md). Use
[Review and supply calculation inputs](review-calculation-values.md) when a
modelo later reports missing casillas, bindings, offsets, or manual values.

Future versions may use attached invoices, PDFs, or other evidence to suggest
rates and richer classifications. That is not implemented in the current LLM
classification command.

## 1. Ask for a suggestion

Find a row that still needs classification:

```bash
aeat app ledger list --filter classification=NOT_YET_PROCESSED
aeat app ledger view <transaction-id>
```

Preview the LLM suggestion:

```bash
aeat app ledger classify --id <transaction-id> --llm claude
```

Use the row description, amount, direction, counterparty, and source documents
to decide whether the suggestion makes sense. For the underlying manual
concepts, see [Classify transactions](classify-transactions.md).

## 2. Review the proposed options

Review the suggested classification first:

- `BUSINESS` means the whole row is business-related.
- `PERSONAL` means the row should not feed tax calculations.
- `MIXED` means part business and part personal.

Then review the suggested category. Expense categories can be listed with:

```bash
aeat app ledger categories
```

If the row is mixed-use, the LLM suggestion alone is not enough. Supply the
business percentage manually with the normal classification workflow:

```bash
aeat app ledger classify --id <transaction-id> --classification MIXED --business-pct 0.5 --category-id <category-id>
```

## 3. Reject, apply, or override

Reject a suggestion by doing nothing else. Preview mode leaves the row
unchanged.

Apply a suggestion only after review:

```bash
aeat app ledger classify --id <transaction-id> --llm claude --apply
```

The applied suggestion is saved to the
[active profile](profile-setup.md#what-the-active-profile-means) ledger with
`llm:` provenance and a local history event. Review it afterwards:

```bash
aeat app ledger view <transaction-id>
aeat app ledger history <transaction-id>
```

Override with a manual classification whenever the suggestion is wrong or
incomplete:

```bash
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id>
```

Manual classification is the correction path. Re-run `ledger preflight` for the
period after important corrections:

```bash
aeat app ledger preflight --period 2026Q1
```

## Batch classification

There is no batch LLM classification command in the current CLI.

The implemented bulk path is CSV-based manual classification:

```bash
aeat app ledger classify --from-csv ./classifications.csv
```

That CSV accepts `transaction_id`, `classification`, and optional
`category_id`. Use [Classify transactions](classify-transactions.md) for the
bounded export, CSV preparation, apply, and review workflow.

For deterministic automatic classification of repeated descriptions, use
stored ledger rules:

```bash
aeat app ledger rule add --description-pattern "software" --classification BUSINESS --category-id <category-id>
aeat app ledger rule apply --dry-run
aeat app ledger rule apply
```

Run the dry run first. Rules apply to active unclassified transactions unless
you explicitly use `--reaffirm`.

## Next steps

- [Set up LLM classification providers](setup-llm-classification.md)
- [Work with Transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
