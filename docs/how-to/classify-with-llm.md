# Classify transactions with an LLM

This page covers the LLM-assisted classification workflow: setting up a
provider, previewing a suggestion for one transaction, the review loop
(apply, reject, or override), saturating the IVA tax fields, and reading an
attached invoice with a model, on your own machine or, with explicit
consent, through a cloud provider. The suggestion is always a starting
point: you confirm or correct it, and the model never sets a euro amount.

Classification does not contact AEAT and does not submit anything. The
provider CLI may contact its own external service depending on your provider
setup; see [the privacy boundary](#privacy-boundary) before using real
taxpayer data.

The LLM and vision commands on this page need a provider CLI or a local vision
model that the documentation sandbox does not run, so they are shown as
display-only frames. The local commands around them run live at build time.

## Before you start

You need:

- An active profile, see [set up your taxpayer profile](profile-setup.md),
  and at least one transaction in its ledger to classify. See
  [Import and manage transactions](import-bank-statements.md).
- Your master-key passphrase. The command opens the encrypted ledger, so it
  prompts for the passphrase.
- A provider CLI installed, on `PATH`, and logged in.

The runtime emits help, prompts, and messages in Spanish.

## Set up a provider

`aeat` does not store LLM credentials and has no separate LLM account
configuration. It runs a provider CLI that is already installed and
authenticated on your system. The classification command accepts provider
names such as `claude`, `antigravity`, and `codex`; `antigravity` uses
Google's `agy` CLI, the supported successor to the retired standalone
`gemini` CLI.

List the provider CLIs visible on `PATH`. Each row reports a provider, its
status (`available` or `unavailable`), and a fix when something is missing:

```{cli-sequence} llm-providers
```

This checks discoverability only, not account login. The local vision reader
appears here too: `ollama-vision` shows `unavailable` with a fix until Ollama
is running. For a wider check that also reports profile service capabilities,
run `aeat config check`; it lists each LLM provider as `disponible` or `ausente`
with the fix for each problem.

Install and authenticate the provider with its own CLI or account flow. The
login command and data-retention settings belong to the provider, not to
`aeat`. Then smoke-test with a preview, which saves nothing:

```{cli-sequence} llm-provider-smoke-test
```

A logged-out provider makes the command refuse and relay the provider's own
error (for example `La clasificacion por LLM fallo: claude CLI exited with
1: 'Not logged in ...'`). Complete that provider's login and retry.

## Ask for a suggestion

Find a row that still needs classification and inspect it. Then send that one
row to the provider for a preview:

```{cli-sequence} llm-suggest
:verify: Confirm the unclassified row is ready to send for a suggestion.
```

`aeat` sends that one row to the selected provider CLI, which suggests a
classification (`BUSINESS`, `PERSONAL`, or `MIXED`), an expense category
when it can choose one from the allowed list, a confidence, and a short
reason. In preview mode nothing is saved. For the full machine-readable
record, including the `provenance` (`llm:<provider>`) and `persisted`
fields, put the global JSON flag before the subcommand:

```{cli-sequence} llm-suggest-json
```

Use the row description, amount, direction, counterparty, and source
documents to decide whether the suggestion makes sense. For the underlying
manual concepts, see [Classify transactions](classify-transactions.md).

## Review, apply, reject, or override

The review loop has four terminals:

- **Review.** Preview without `--apply`. Nothing is saved; walking away
  leaves the row unchanged.
- **Apply.** Persist the suggestion after review. The apply output shows the
  transaction id, `clasificado-por llm:<provider>`, and the new review status;
  provenance, confidence, and reason are recorded with the classification event.
- **Reject.** Record that the model was wrong, with your reason, as an audit
  event; the row stays unclassified and the record stays in history. `--reject`
  cannot be combined with `--apply`. Previewing and walking away also changes
  nothing, but `--reject` is what writes the audit trail.
- **Override.** Classify manually whenever the suggestion is wrong or
  incomplete. Manual classification always wins and supersedes a derived or
  model-applied value.

Apply and reject both run the provider, so they are shown as display-only
frames:

```{cli-sequence} llm-apply-reject
```

Override runs entirely on your machine. Classify the row by hand with the
classification and category you choose:

```{cli-sequence} llm-override
:verify: Confirm the manual override classifies the row.
```

If the row is mixed-use, the LLM suggestion alone is not enough; supply the
business share through the normal
[mixed-use workflow](classify-transactions.md#classify-mixed-use-transactions).
After important corrections, re-run preflight for the period:

```{cli-sequence} llm-preflight
:verify: Confirm the period preflight reads ready after corrections.
```

## Fill in the tax fields automatically

A plain applied suggestion saves the classification and the expense
category; it does not fill in the regulated tax fields. Add `--saturate` to
also select an IVA category and derive the taxable base, IVA rate, and IVA
amount. The model never invents a number: it only selects the IVA category;
the rate comes from the registry, and the base and IVA amount are computed
from the transaction total:

```{cli-sequence} llm-saturate
```

The preview adds the selected IVA category and, when the category has a
Spanish rate, the derived figures; base and IVA always add up to the
transaction total. A category with no simple Spanish rate (an
intra-community supply, a reverse-charge purchase) shows a note instead of
numbers, and you complete those by hand. The model may also decline and
return `unknown` rather than guess; re-run, or pick the category yourself.

When you already know the IVA category, or the model returned `unknown`,
classify the row as business first, then let the system derive the numbers
without any `--llm`. This derives the figures from the official rate exactly
as the model path does and records them as system-derived. It only touches
the IVA fields, and the row must already be classified business or mixed:

```{cli-sequence} llm-derive-iva
:verify: Confirm the derived IVA fields land without any provider.
```

To override any field by hand, classify manually with the figures yourself.
The taxable base plus IVA must equal the transaction total to the cent:

```{cli-sequence} llm-manual-figures
:verify: Confirm the hand-entered IVA figures land on the row.
```

IRPF category is still entered manually in
[Classify transactions](classify-transactions.md). Use
[Review and supply calculation inputs](review-calculation-values.md) when a
modelo later reports missing values.

## Read the attached invoice

Attach a purchase invoice or receipt to a transaction (see
[Attach invoices and receipts](ledger-evidence.md)), then let the model read
it while classifying with `--read-evidence`. The model chooses the spending
category and the IVA situation from what it reads; `aeat` derives every euro
amount from the registry. How the document is read depends on the file:

- **A scanned PDF or an image** is read on your own machine by a local
  vision model. Nothing leaves the machine, no acknowledgement is needed, no
  `--llm` provider is needed, and it works in gestor and professional
  deployments.
- **A text-layer PDF** has its text extracted and sent to a cloud provider
  (the same `--llm` providers). This sends the text off your machine, so it
  is off by default, barred for gestor deployments, and gated behind an
  explicit per-run acknowledgement.

Prefer the on-host path. Install Ollama and pull the default vision model
first (this is an Ollama command, not an `aeat` command):

```bash
ollama pull qwen2.5vl:3b
```

`qwen2.5vl:3b` is about 3 GB and runs on a consumer GPU or on CPU. On an
8 GB or larger GPU, pull `qwen2.5vl:7b` for stronger reading of dense scans;
for a low-memory or CPU-only machine, pull `moondream`. Then classify from
the attached image, previewing first. Override the vision model for one run
with `--vision-model qwen2.5vl:7b`:

```{cli-sequence} llm-read-evidence-local
```

Reading a text-layer PDF through a cloud provider requires all of the
following, or the command refuses and explains why:

- The installation permits it. Cloud evidence reads are off by default
  and stay off in gestor installations; whoever administers the
  installation decides this deployment setting.
- You acknowledge it on this run with `--evidence-acknowledged`. The
  acknowledgement is never remembered; pass it every time.

```{cli-sequence} llm-read-evidence-cloud
```

The acknowledgement gates the upload of the invoice text only. A transaction
with no attached evidence sends nothing extra: the provider receives only
the transaction row, exactly as in the plain suggestion flow.

### Split a multi-line invoice automatically

When the model reads an invoice with several lines at different rates or
categories, the preview adds a `split recommended` note with the exact
command to separate them. Each line must become its own entry so its
deductible IVA and base-rate expense file independently. To act on it in one
step, add `--auto-split`. `--auto-split` requires `--read-evidence` and cannot
combine with the manual override flags:

```{cli-sequence} llm-auto-split
```

A multi-line invoice previews one child transaction per line, each with its
own category, IVA category, and registry-derived base and IVA; the children
sum exactly to the original amount. A single-line invoice is classified in
place with no split.

### How `aeat` protects the documents it reads

- Invoice bytes live only in encrypted secure storage. Reading decrypts them
  into memory for the one call and never writes them to a temp file, a log,
  or a cache.
- A scanned or image read sends the image only to the local model over a
  loopback connection on your machine. Nothing leaves the machine.
- A text-layer read sends only the extracted text, and only to a cloud
  provider you explicitly permitted and acknowledged. It never sends the PDF
  bytes.
- The model selects only the classification, the category, the IVA category,
  and a split proportion. `aeat` derives every rate, base, and IVA amount
  from the registry, and refuses to persist a result whose parts do not add
  up. When the printed IVA does not match the computed IVA, the review shows
  an advisory so you can check before filing.

### Evidence deployment settings

Consent and model settings are deployment configuration, off by default
and administered outside this workflow. The full list lives in the
[environment overrides reference](../reference/environment-overrides.md).

## See how each suggestion was produced

Every applied result records how it was produced, so a later review shows
the source:

- `llm:local-vision:<model>`: read on-host by the local vision model.
- `llm:<provider>:<model>`: classified by a cloud provider.
- `derived:iva-category`: you chose the IVA category and `aeat` derived the
  rest.
- `manual`: you set the classification by hand.

Inspect a transaction and its history at any time:

```{cli-sequence} llm-inspect-history
:verify: Confirm the transaction's history records its events.
```

## Limits and batch alternatives

The LLM path is single-transaction only; it cannot be combined with
`--from-csv` or manual `--classification` flags. For bulk work use the
CSV-based manual path (`aeat app ledger classify --from-csv
./classifications.csv`) or deterministic stored rules (`aeat app ledger rule
add` then `rule apply --dry-run` then `rule apply`); both are covered in
[Classify transactions](classify-transactions.md).

## Privacy boundary

LLM classification calls the selected provider CLI on your machine. That CLI
may send prompt data to the provider's cloud service, depending on how that
provider works and how your account is configured. Treat transaction
descriptions, counterparties, amounts, categories, and any profile context
in the prompt as taxpayer data. Do not use production data with an LLM
provider unless your provider setup and privacy policy permit it.

## Next steps

- [Classify transactions](classify-transactions.md)
- [Attach invoices and receipts](ledger-evidence.md)
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
