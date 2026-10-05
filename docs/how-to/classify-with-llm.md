# Classify transactions with an LLM

This page covers large language model (LLM) assisted classification: setting up the local reader, previewing a suggestion for one transaction, the review loop (apply, reject, or override), filling in the VAT tax fields, and reading an attached invoice with a model. Every model runs on your own machine. The suggestion is always a starting point: you confirm or correct it, and the model never sets a euro amount.

Classification does not contact AEAT and does not submit anything. It also
sends nothing to a cloud service. See [the privacy boundary](#privacy-boundary)
for the one command that can.

The LLM commands on this page need a local model runtime that the documentation sandbox does not run, so they are shown as examples that are not run. The local commands around them run live at build time.

## Before you start

You need:

- An active profile, see [set up your taxpayer profile](profile-setup.md),
  and at least one transaction in its records to classify. See
  [Import and manage transactions](import-bank-statements.md).
- Your passphrase. The command opens your encrypted records, so it prompts for the passphrase.
- The `llm` extra, installed through your install channel, for example
  `pip install "cadrumo[llm]"`.
- A local model runtime with its models, set up in the next section.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you
[choose another language](profile-setup.md#choose-the-output-language).

(set-up-a-provider)=
## Set up the local reader

`aeat` sends every classification prompt to a model runtime on your own
computer, over a loopback connection. It stores no LLM credentials and needs
no account. The `llm` extra provides the client, and `aeat config provision`
installs the runtime and its models.

To set up everything in one run, use:

```{cli-sequence} llm-provision-setup
```

Setup installs the runtime with the platform package manager (winget on
Windows, Homebrew on macOS), starts it, downloads a model for each reader
role, loads the models, and verifies them. On Linux, install the runtime
yourself. Without `--confirm`, setup stops before it installs anything. Steps
that are already done are reported as unchanged. See
[Install Cadrumo](../workstation-setup.md) for the whole sequence.

Text reads use the `qwen3:1.7b` model by default. Scanned and image reads use
`qwen3-vl:2b`. Check the result with `aeat config check`. It reports the
profile's service capabilities, whether each local reader is available, and
the fix for each problem. `aeat config provision status` reports the runtime
and each reader model in detail. If it reports that no fitness check is
recorded for the text model, run `aeat config provision verify`.

The profile capability `llm_vision` is on by default. To stop `aeat` from reading scanned or image supporting documents, turn that capability off with `aeat config profile capabilities set`, naming `llm_vision` and `off`. Reads of scanned or image supporting documents then refuse.

Smoke-test the setup with a preview, which saves nothing:

```{cli-sequence} llm-provider-smoke-test
```

If the runtime is not running or a model is missing, the command refuses and
reads nothing. The refusal points to `aeat config provision status`, then to
`aeat config provision start` and `aeat config provision pull`. Fix the gap
and retry.

## Ask for a suggestion

Find a row that still needs classification and inspect it. Then send that one
row to the local model for a preview:

```{cli-sequence} llm-suggest
:verify: Confirm the unclassified row is ready to send for a suggestion.
```

`aeat` sends that one row to the local text model, which suggests a
classification (`BUSINESS`, `PERSONAL`, or `MIXED`), an expense category
when it can choose one from the allowed list, a confidence, and a short
reason. In preview mode nothing is saved. For the full machine-readable
record, including the `provenance` (`llm:local-text:<model>`) and `persisted`
fields, put the global JSON flag before the subcommand:

```{cli-sequence} llm-suggest-json
```

Use the row description, amount, direction, counterparty, and supporting documents to decide whether the suggestion makes sense. For the underlying
manual concepts, see [Classify transactions](classify-transactions.md).

## Review, apply, reject, or override

The review loop has four terminals:

- **Review.** Preview without `--apply`. Nothing is saved; walking away
  leaves the row unchanged.
- **Apply.** Persist the suggestion after review. The apply output shows the transaction id, a `classified-by` line with `llm:local-text:<model>`, and the new review status. Where the suggestion came from, its confidence, and the reason are recorded with the classification event.
- **Reject.** Record that the model was wrong, with your reason, as an audit
  event; the row stays unclassified and the record stays in history. `--reject`
  cannot be combined with `--apply`. Previewing and walking away also changes
  nothing, but `--reject` is what writes the audit trail.
- **Override.** Classify manually whenever the suggestion is wrong or
  incomplete. Manual classification always wins and supersedes a derived or
  model-applied value.

Apply and reject both run the model, so they are shown as examples that are not run:

```{cli-sequence} llm-apply-reject
```

Override runs without the model. Classify the row by hand with the
classification and category you choose:

```{cli-sequence} llm-override
:verify: Confirm the manual override classifies the row.
```

If the row is mixed-use, the LLM suggestion alone is not enough. Supply the
business share through the normal
[mixed-use workflow](classify-transactions.md#classify-mixed-use-transactions).
After important corrections, re-run preflight for the period:

```{cli-sequence} llm-preflight
:verify: Confirm the period preflight reads ready after corrections.
```

## Fill in the tax fields automatically

A plain applied suggestion saves the classification and the expense
category; it does not fill in the regulated tax fields. Add `--saturate` to
also select a VAT category and derive the taxable base, VAT rate, and VAT
amount. The model never invents a number: it only selects the VAT category;
the rate comes from the official rates Cadrumo holds, and the base and VAT amount are computed
from the transaction total:

```{cli-sequence} llm-saturate
```

The preview adds the selected VAT category and, when the category has a
Spanish rate, the derived figures. Base and VAT always add up to the
transaction total. A category with no simple Spanish rate (an
intra-community supply, a reverse-charge purchase) shows a note instead of
numbers, and you complete those by hand. The model may also decline and
return `unknown` rather than guess. Re-run, or pick the category yourself.

If you already know the VAT category, or the model returned `unknown`,
classify the row as business first. Then let the system derive the numbers
without `--llm`. This derives the figures from the official rate exactly
as the model path does and records them as system-derived. It only touches
the VAT fields, and the row must already be classified business or mixed:

```{cli-sequence} llm-derive-iva
:verify: Confirm the derived VAT fields land without any model.
```

To override any field by hand, classify manually with the figures yourself.
The taxable base plus VAT must equal the transaction total to the cent:

```{cli-sequence} llm-manual-figures
:verify: Confirm the hand-entered VAT figures land on the row.
```

IRPF category is still entered manually in
[Classify transactions](classify-transactions.md). Use
[Review and supply calculation inputs](review-calculation-values.md) when a
modelo later reports missing values.

A VAT category does not by itself make input VAT deductible. To deduct it, also pass `--deduction-kind` (for example `domestic_current`) on `aeat app ledger classify` or `add`. The kind `domestic_current` needs a purchase invoice linked as a supporting document. See [Attach invoices and receipts to transactions](ledger-evidence.md).

## Read the attached invoice

Attach a purchase invoice or receipt to a transaction (see [Attach invoices and receipts to transactions](ledger-evidence.md)), then let the model read it while classifying with `--read-evidence`. The model chooses the spending category and the VAT situation from what it reads; `aeat` derives every euro amount from the official rates. Both kinds of document are read on your own machine:

- **A scanned PDF or an image** is read by the local vision model. The
  `llm_vision` capability must be on, which is the default.
- **A text-layer PDF** has its text extracted and read by the local text
  model.

Neither read needs an acknowledgement, and both work in gestor and
professional deployments. `--read-evidence` on its own is enough. `--llm`
without `--read-evidence` classifies from the transaction row only and never
reads the attached document. To read the attached document with the vision model
you provisioned, preview first:

```{cli-sequence} llm-read-evidence-local
```

Pull a different model with `aeat config provision pull --model <model>`. For
example, use `qwen2.5vl:7b` on a computer with room for it. To use it for one
scanned or image read, add `--vision-model qwen2.5vl:7b` to the classify
command.

A transaction with no attached supporting document sends nothing extra: the model receives only the transaction row, exactly as in the plain suggestion flow.

### Split a multi-line invoice automatically

When the model reads an invoice with several lines at different rates or
categories, the preview adds a `split recommended` note with the exact
command to separate them. Each line must become its own entry so its
deductible VAT and base-rate expense file independently. To act on it in one
step, add `--auto-split`. `--auto-split` requires `--read-evidence` and cannot
combine with the manual override flags:

```{cli-sequence} llm-auto-split
```

A multi-line invoice previews one child transaction per line, each with its
own category, VAT category, and derived base and VAT; the children
sum exactly to the original amount. A single-line invoice is classified in
place with no split.

### How `aeat` protects the documents it reads

- Invoice bytes live only in encrypted secure storage. Reading decrypts them
  into memory for the one call and never writes them to a temp file, a log,
  or a cache.
- A read sends the image or the extracted text only to the local model over a
  loopback connection on your machine. Nothing leaves the machine.
- The model selects only the classification, the category, the VAT category,
  and a split proportion. `aeat` derives every rate, base, and VAT amount from the official rates, and refuses to persist a result whose parts do not add
  up. When the printed VAT does not match the computed VAT, the review shows
  an advisory so you can check before filing.

## See how each suggestion was produced

Every applied result records how it was produced, so a later review shows
the source:

- `llm:local-vision:<model>`: read by the local vision model.
- `llm:local-text:<model>`: classified by the local text model.
- `derived:iva-category`: you chose the VAT category and `aeat` derived the
  rest.
- `manual`: you set the classification by hand.

Inspect a transaction and its history at any time:

```{cli-sequence} llm-inspect-history
:verify: Confirm the transaction's history records its events.
```

## Limits and batch alternatives

The LLM path is single-transaction only; it cannot be combined with
`--file` or manual `--classification` flags. For bulk work use the
CSV-based manual path (`aeat app ledger classify --file
./classifications.csv`) or deterministic stored rules (`aeat app ledger rule
add` then `rule apply --dry-run` then `rule apply`); both are covered in
[Classify transactions](classify-transactions.md).

(privacy-boundary)=
## Privacy boundary

Classification calls only the model runtime on your own machine, over a
loopback connection. No transaction description, counterparty, amount, or
document leaves the machine, and `aeat` needs no LLM account or key for it.
This holds for the default endpoint: if you point `CADRUMO_LLM_OLLAMA_CHAT_URL`
at a runtime on another host, reads go to that host.

One command can send a document off your machine:
`aeat app ledger evidence extract --off-host-provider <provider>`. It reads
invoice fields, not classifications, and it is off by default. It runs only
when the deployment permits off-host reads, the profile's
`cloud_evidence_upload` capability is on, and you pass
`--acknowledge-off-host` for that one read. Gestor deployments never allow it.
Reading with the Anthropic API also needs the `anthropic` extra. Treat the
document as taxpayer data before you use it. The settings that govern it are
in the [environment overrides reference](../reference/environment-overrides.md).

## Next steps

- [Classify transactions](classify-transactions.md)
- [Attach invoices and receipts to transactions](ledger-evidence.md)
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
