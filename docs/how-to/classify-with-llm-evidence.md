# Classify a transaction from its invoice with a model

Use this guide to classify a ledger transaction by reading its attached invoice
or receipt with a model. The model chooses the spending category and the IVA
(Value Added Tax) situation from what it reads; `aeat` derives every euro amount
from the registry. The model never sets a number.

This builds on [Classify transactions with an LLM](classify-with-llm.md), which
covers model-assisted classification from the transaction row alone. Read that
guide first if you have not used `--llm` yet. To attach the invoice this guide
reads, see [Attach invoices and receipts](ledger-evidence.md).

## How evidence is read: on-host or off-host

`aeat` reads attached evidence one of two ways, decided by the file:

- **A scanned PDF or an image** is read on your own machine by a local vision
  model. Nothing leaves the machine, and you need no acknowledgement.
- **A text-layer PDF** has its text extracted and sent to a cloud provider
  (the same `--llm` providers). This sends the text off your machine, so it is
  off by default, barred for gestor deployments, and gated behind an explicit
  per-run acknowledgement.

Prefer the on-host path. It needs no acknowledgement and keeps the document on
your machine.

## Read a scanned or image invoice on-host

Reading an image runs entirely on your machine through a local Ollama vision
model. You do not pass `--llm`, and no acknowledgement applies.

Install Ollama, then pull the default vision model:

```bash
ollama pull qwen2.5vl:3b
```

`qwen2.5vl:3b` is about 3 GB and runs on a consumer GPU or on CPU. For stronger
reading on an 8 GB or larger GPU, pull `qwen2.5vl:7b`. For a low-memory or
CPU-only machine, pull `moondream`.

Classify a transaction from its attached image, letting the model pick the IVA
category:

```bash
aeat app ledger classify <transaction-id> --read-evidence --saturate
```

This previews the result without saving. Add `--apply` to persist it:

```bash
aeat app ledger classify <transaction-id> --read-evidence --saturate --apply
```

Override the vision model for one run:

```bash
aeat app ledger classify <transaction-id> --read-evidence --saturate --vision-model qwen2.5vl:7b
```

## Read a text-layer PDF through a cloud provider

A text-layer PDF is read by extracting its text and sending that text to a cloud
provider. This sends the document text off your machine, so `aeat` requires all
of the following:

- The deployment permits it. An administrator sets
  `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED=1`. It is off by default.
- The deployment is not in gestor mode. `AEAT_EVIDENCE_GESTOR_MODE=1`
  categorically bars cloud evidence reading, whatever else is set.
- You acknowledge it on this run with `--evidence-acknowledged`. The
  acknowledgement is never remembered; pass it every time.

```bash
aeat app ledger classify <transaction-id> --llm claude --read-evidence --evidence-acknowledged --saturate
```

Without the acknowledgement, the command refuses and explains that reading
text-layer evidence sends it to a cloud model. Scanned or image evidence is
read on-host and needs none of this.

## Split a multi-line invoice automatically

When the model reads an invoice with several lines at different rates or
categories, it reports that the invoice has multiple components and suggests a
split. The suggestion arrives as a notice with the exact command to run.

To act on it in one step, add `--auto-split`:

```bash
aeat app ledger classify <transaction-id> --read-evidence --auto-split
```

`aeat` previews one child transaction per invoice line, each with its own
category and IVA. The children's base and IVA sum exactly to the parent. Add
`--apply` to persist the split. A single-line invoice is classified in place
with no split. `--auto-split` requires `--read-evidence` and cannot combine with
the manual override flags.

## Review, approve, reject, or override

Reading evidence follows the same review loop as any model suggestion:

- **Review.** Run the command without `--apply` to preview. Nothing is saved.
- **Approve.** Add `--apply` to persist the suggestion.
- **Reject.** Do nothing. An unapplied preview changes nothing and records no
  event.
- **Override.** Set the classification yourself with `--classification` and
  `--category-id`. The manual path cannot combine with `--llm`.

If the model returns `unknown` for the IVA category, choose a category yourself
and let `aeat` derive the rest:

```bash
aeat app ledger classify <transaction-id> --iva-category domestic_general_21 --saturate
```

## How `aeat` protects the documents it reads

- Invoice bytes live only in encrypted secure storage. Reading decrypts them
  into memory for the one call and never writes them to a temp file, a log, or
  a cache.
- A scanned or image read sends the image only to the local model over a
  loopback connection on your machine. Nothing leaves the machine.
- A text-layer read sends only the extracted text, and only to a cloud provider
  you explicitly permitted and acknowledged. It never sends the PDF bytes.
- The model selects only the classification, the category, the IVA category,
  and a split proportion. `aeat` derives every rate, base, and IVA amount from
  the registry, and refuses to persist a result whose parts do not add up.

## Provenance you can audit

Every applied result records how it was produced, so a later review shows the
source:

- `llm:local-vision:<model>`: read on-host by the local vision model.
- `llm:<provider>:<model>`: classified by a cloud provider.
- `derived:iva-category`: you chose the IVA category and `aeat` derived the
  rest.
- `manual`: you set the classification by hand.

Inspect a transaction and its history:

```bash
aeat app ledger view <transaction-id>
aeat app ledger history <transaction-id>
```

## Settings reference

These settings are environment variables. The evidence-consent settings default
to the safest value:

| Setting | Default | Effect |
| --- | --- | --- |
| `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED` | off | Must be on to allow any cloud evidence read |
| `AEAT_EVIDENCE_GESTOR_MODE` | off | When on, bars cloud evidence reading entirely |
| `AEAT_LLM_OLLAMA_VISION_MODEL` | `qwen2.5vl:3b` | The local vision model for image reads |
| `AEAT_LLM_OLLAMA_NUM_CTX` | `8192` | The local model context window |
| `AEAT_LLM_VISION_READ_TIMEOUT_S` | `300` | Seconds to wait for a local vision read |

## Next steps

- [Set up a provider for LLM classification](setup-llm-classification.md)
- [Classify transactions with an LLM](classify-with-llm.md)
- [Attach invoices and receipts](ledger-evidence.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
