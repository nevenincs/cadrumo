# Classify transactions with an LLM

Use this after the ledger row exists in [Work with Transactions](import-bank-statements.md).
If the provider CLI is not installed, on `PATH`, and authenticated already,
start with [Set up LLM classification providers](setup-llm-classification.md).

```bash
aeat app ledger classify <transaction-id> --llm claude
```

That command asks the `claude` provider for a suggestion and previews the
result. It does not save anything. Use `antigravity` or `codex` instead of
`claude` when that is the provider CLI you have configured.

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

A plain applied LLM suggestion saves the classification (business, personal, or
mixed) and the suggested expense category. It does not fill in the regulated
tax fields. Add `--saturate` to also select an IVA category and derive the
taxable base, IVA rate, and IVA amount (see [Saturate the tax fields](#saturate-the-tax-fields)).
IRPF category is still entered manually in
[Classify transactions](classify-transactions.md). Use
[Review and supply calculation inputs](review-calculation-values.md) when a
modelo later reports missing values.

The model never invents a number. With `--saturate` it only selects the IVA
category; the rate comes from the registry and the base and IVA amount are
computed from the transaction total.

## 1. Ask for a suggestion

Find a row that still needs classification:

```bash
aeat app ledger list --filter classification=NOT_YET_PROCESSED
aeat app ledger view <transaction-id>
```

Preview the LLM suggestion:

```bash
aeat app ledger classify <transaction-id> --llm claude
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
aeat app ledger classify <transaction-id> --classification MIXED --business-pct 0.5 --category-id <category-id>
```

## 3. Reject, apply, or override

Reject a suggestion by doing nothing else. Preview mode leaves the row
unchanged.

Apply a suggestion only after review:

```bash
aeat app ledger classify <transaction-id> --llm claude --apply
```

The applied suggestion is saved to the active profile's ledger. It records
that an LLM was used, along with the confidence and reason. Review it
afterwards:

```bash
aeat app ledger view <transaction-id>
aeat app ledger history <transaction-id>
```

Override with a manual classification whenever the suggestion is wrong or
incomplete:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --category-id <category-id>
```

Manual classification is the correction path. Re-run `ledger preflight` for the
period after important corrections:

```bash
aeat app ledger preflight --year 2026 --period 1T
```

## Saturate the tax fields

Add `--saturate` to also select an IVA category and derive the tax substrate.

Preview a saturated suggestion:

```bash
aeat app ledger classify <transaction-id> --llm claude --saturate
```

The preview adds the selected IVA category and, when the category has a Spanish
rate, the derived taxable base, IVA rate, and IVA amount. The base and IVA
amount always add up to the transaction total. A category with no simple
Spanish rate (for example an intra-community supply or a reverse-charge
purchase) shows a short note instead of numbers, and you complete those by hand.

The model may also decline to pick an IVA category and return `unknown`, even
for an ordinary domestic purchase — it chooses not to guess. When that happens
no numbers are derived. Re-run the suggestion (a different provider may decide),
or complete the IVA fields by hand, as the override below shows.

Apply a saturated suggestion after review:

```bash
aeat app ledger classify <transaction-id> --llm claude --saturate --apply
```

Override any field by classifying manually afterwards. Manual classification
always wins. The tool only derives the base, rate, and amount through
`--saturate`; when you set the IVA category by hand you also supply the figures
yourself — passing `--iva-category` alone records the category but does not
compute the numbers:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --iva-category domestic_reduced_10 --taxable-base 110.00 --iva-rate 0.10 --iva-amount 11.00
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

## Read attached evidence

Attach a purchase invoice or receipt to a transaction, then let the model read it
while classifying. The text is extracted from the document on your machine; only
that text reaches the classifier. The document bytes stay in secure storage.

Reading evidence with a cloud provider (claude, codex, antigravity) sends the
extracted text off your machine. This is off by default. Enable it for the
deployment, then acknowledge the upload each time:

```bash
aeat app ledger classify <transaction-id> --llm claude --saturate --read-evidence --evidence-acknowledged
```

Acknowledge the upload every time. Evidence reading is not available in gestor or
professional deployments.

The model reads the document only to choose the spending category and the IVA
situation. It never copies a euro amount from the invoice. The tax numbers are
always computed from the official rates. When the printed IVA does not match the
computed IVA, the review shows an advisory so you can check before filing.

## Next steps

- [Set up LLM classification providers](setup-llm-classification.md)
- [Work with Transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
