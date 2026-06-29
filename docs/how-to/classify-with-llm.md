# Classify transactions with an LLM

Use this after the ledger row exists in [Work with Transactions](import-bank-statements.md).
If the provider CLI is not installed, on `PATH`, and authenticated already,
start with [Set up LLM classification providers](setup-llm-classification.md).

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md) - and
  at least one transaction in its ledger to classify.
- Your master-key passphrase. The command opens the encrypted ledger, so it
  prompts for the passphrase (or reads `AEAT_SECRET_PASSPHRASE` when set).
- The provider CLI installed, on `PATH`, and logged in. A logged-out provider
  makes the command refuse and relay the provider's own error (for example
  `La clasificacion por LLM fallo: claude CLI exited with 1: 'Not logged in ...'`).

The runtime emits help, prompts, and messages in Spanish.

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

The default preview output shows the transaction id, the suggested
classification, the suggested category when present, the confidence, and the
reason, followed by a line telling you to re-run with `--apply`,
`--classification`, or nothing. In preview mode nothing is saved.

For the full machine-readable record - including the provider, the `provenance`
(`llm:<provider>`), and `persisted` (`false` in preview) - run the same command
with the global JSON flag before the subcommand:

```bash
aeat --format json app ledger classify <transaction-id> --llm claude
```

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

The review loop has four terminals: review (preview), approve (`--apply`), reject
(`--reject`), and override (manual classify).

Reject a suggestion when the model is wrong and you want the decision on record:

```bash
aeat app ledger classify <transaction-id> --llm claude --reject --reason "this is personal"
```

Reject records what the model proposed and your reason as an audit event. The row
is left unclassified. The next `aeat app ledger view <transaction-id>` flags that
the most recent LLM suggestion was rejected, and the full record stays in history:

```bash
aeat app ledger view <transaction-id>
aeat app ledger history <transaction-id>
```

`--reject` cannot be combined with `--apply`. Simply previewing and walking away
also leaves the row unchanged, but `--reject` is what writes the audit trail.

Apply a suggestion only after review:

```bash
aeat app ledger classify <transaction-id> --llm claude --apply
```

The applied suggestion is saved to the active profile's ledger. The apply
output shows the transaction id, `clasificado-por llm:<provider>`, and the new
review status; the provenance, confidence, and reason are recorded with the
classification event. Review it afterwards:

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
or pick the category yourself and let the system derive the numbers, as
[Derive the IVA fields yourself](#derive-the-iva-fields-yourself) shows.

Apply a saturated suggestion after review:

```bash
aeat app ledger classify <transaction-id> --llm claude --saturate --apply
```

## Split a multi-line invoice automatically

Read the attached invoice while you classify. Add `--read-evidence`:

```bash
aeat app ledger classify <transaction-id> --read-evidence --saturate
```

When the invoice carries several lines at different rates or categories, the
preview adds a `split recommended` note with the exact command to separate them.
Each line must become its own entry so its deductible IVA and base-rate expense
file independently.

Action the split with `--auto-split`. Preview it first:

```bash
aeat app ledger classify <transaction-id> --read-evidence --auto-split
```

The model reads the invoice and decides. A multi-line invoice previews one child
per line, each with its own category, IVA category, and registry-derived base and
IVA. A single-line invoice previews a normal in-place classification instead.

Apply the decision:

```bash
aeat app ledger classify <transaction-id> --read-evidence --auto-split --apply
```

A multi-line invoice is split into children that sum exactly to the original
amount. A single-line invoice is classified in place. The model never writes a
number; the registry derives every base and IVA. Review the result:

```bash
aeat app ledger view <transaction-id>
```

Add `--llm claude` to read a text-layer PDF through your cloud provider, or omit
it to read a scanned or image invoice on your own machine. Add `--vision-model
qwen2.5vl:7b` for stronger reading of a dense scan.

## Derive the IVA fields yourself

When you already know the IVA category — or the model returned `unknown` — pick
the category yourself and let the system derive the numbers. Classify the row
as a business expense first, then run `--saturate` with `--iva-category` and no
`--llm`:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --category-id <category-id>
aeat app ledger classify <transaction-id> --iva-category domestic_general_21 --saturate
```

The second command derives the taxable base, IVA rate, and IVA amount from the
official rate for that category and the transaction total, exactly as the model
path does. It records that the numbers were system-derived, not hand-entered. It
only touches the IVA fields; the business classification you chose first stays as
it is. The row must already be classified business or mixed — IVA applies only to
business activity.

A category with no simple Spanish rate (an intra-community supply, a
reverse-charge purchase) cannot be derived this way; the command says so and you
complete those figures by hand, as the manual override below shows.

## Override the fields by hand

Override any field by classifying manually. Manual classification always wins
and supersedes a derived or model-applied value. Set the IVA category together
with the figures yourself:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS --iva-category domestic_reduced_10 --taxable-base 110.00 --iva-rate 0.10 --iva-amount 11.00
```

## Batch classification

There is no batch LLM classification command in the current CLI.

The implemented bulk path is CSV-based manual classification:

```bash
aeat app ledger classify --from-csv ./classifications.csv
```

That CSV accepts `transaction_id`, `classification`, and optional columns such
as `category_id`, `business_pct`, `usage_ratio_id`, taxable-base and IVA
fields, `iva_category`, and `irpf_category`. Use
[Classify transactions](classify-transactions.md) for the bounded export, CSV
preparation, apply, and review workflow.

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

For the full evidence workflow, including the on-host vision-model setup, the
consent rules, and the privacy guarantees, see
[Classify a transaction from its invoice with a model](classify-with-llm-evidence.md).
This section is the short version.

Attach a purchase invoice or receipt to a transaction, then let the model read it
while classifying. The document bytes always stay in secure storage; nothing is
written to a temporary file. How the document is read depends on its kind.

A PDF with a text layer is read on your machine, and only the extracted text is
sent to the cloud provider (claude, codex, antigravity). Sending that text off
your machine is off by default and barred for gestor or professional
deployments. Enable it for the deployment, then acknowledge the upload each time:

```bash
aeat app ledger classify <transaction-id> --llm claude --saturate --read-evidence --evidence-acknowledged
```

A scanned PDF or an image invoice is read entirely on your machine by a local
vision model. Nothing leaves the host, so no acknowledgement is needed, no
`--llm` provider is needed, and it works in gestor and professional deployments:

```bash
aeat app ledger classify <transaction-id> --saturate --read-evidence
```

Install a local Ollama vision model first. The default is `qwen2.5vl:3b`
(`ollama pull qwen2.5vl:3b`), which reads invoices well and runs on normal
consumer hardware (a modest GPU or CPU). On an 8 GB+ GPU, override to
`qwen2.5vl:7b` for stronger reading; for CPU-only or low-memory machines, use
`moondream`. See [Set up LLM classification providers](setup-llm-classification.md).

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
