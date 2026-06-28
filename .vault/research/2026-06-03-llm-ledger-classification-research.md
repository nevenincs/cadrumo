---
tags:
  - '#research'
  - '#llm-ledger-classification'
date: '2026-06-03'
modified: '2026-06-03'
related: []
---



# `llm-ledger-classification` research: `LLM transaction classification: built-but-unwired investigation`

Transaction classification is the operator's heaviest burden. The project
intends LLM assistance to be a pivotal ledger feature: the operator should
leverage LLM tools for actual classification, evidence-based base/IVA
separation, and be able to override, manually change, and reject LLM
classifications. Two parallel read-only investigations mapped what exists
versus what an operator can actually reach.

## Findings

### F1 LLM classification is built but unwired to any operator path

Two independent LLM subsystems exist; neither is reachable by an operator and
neither classifies transactions in production:

- `aeat.domain.transactions._llm` ships a mature subprocess classifier:
  `LLMClassifier` protocol (`decided_by` plus
  `classify(transaction) -> LLMClassificationResponse`),
  `SubprocessLLMClassifier` shelling to local `claude` / `gemini` / `codex`
  CLIs, a parametric `PromptSpec`, strict JSON `parse_response` with a
  hallucination guard (rejects any classification/category outside the
  allow-list), a tier model (`MINIMUM_CLASSIFICATION_TIER = MEDIUM`), and a
  `resolve_classifier(provider)` registry. Its only caller is a self-skipping
  live test; no CLI verb, application service, or repository action invokes it.
- `aeat.adapters.outbound.llm` ships a generic `LLMClient.complete` with
  Anthropic / OpenAI / Gemini / Ollama adapters, on-disk cache, pricing, and
  usage tracking, driven by `AEAT_LLM_*` settings. Its seeded prompts are
  translation / casilla-extract / manual-rule-extract only — none classify a
  transaction. It is referenced only inside its own package and tests.

`aeat app ledger classify` is 100 percent manual flag entry
(`--classification` plus the tax-fact flags), routed through
`update_manual_transaction_fields`. `import` lands rows as
`NOT_YET_PROCESSED` and never auto-classifies. There is no `--llm` /
`--suggest` / `--accept` / `--reject` anywhere in the CLI tree, and no operator
config verb for an LLM provider/key (only `AEAT_LLM_*` env vars, which feed the
unwired API client). Net: the feature is roughly 80 percent built and 0 percent
operator-reachable.

### F2 The classifier output covers only a fraction of the classification burden

`LLMClassificationResponse` carries exactly four fields: `classification`
(restricted to BUSINESS / PERSONAL / MIXED / PROCESSED_UNCLASSIFIED),
`confidence` (0..1), `reason`, and an optional `category` (only when the
category-enabled `prompt_spec_with_every_spending_category` is used; the
default spec is classification-only). It does NOT produce the heavy tax
dimensions the operator sets by hand: `taxable_base`, `iva_rate`,
`iva_amount`, `iva_category`, `irpf_category`, `counterparty_eu_member_state`,
or the MIXED business percentage. The `Transaction` model already carries all
those fields; nothing populates them via LLM.

### F3 Evidence-based base/IVA separation does not exist in production

The inverse split (a gross amount to base plus IVA, e.g. 121 -> 100 + 21 at
21 percent) appears only as arithmetic inside two corpus-fidelity tests. The
IVA aggregation layer requires `taxable_base`, `iva_amount`, and `iva_rate` to
be present already and gates with a missing-fact reason otherwise; it never
derives them. The classifier prompt is fed only the raw transaction fields
(dates, amount, currency, counterparty, description) — no attached evidence,
receipt, or invoice — and the response has no base/IVA fields. There is no
LLM-driven and no production rule-based base/IVA separation.

### F4 Override / manual-change / reject mechanics today are manual or regex only

Classification provenance lives on `Transaction.classified_by` (manual, or
`rule:<id>`); no `llm:*` provenance is ever persisted because nothing calls the
classifier. An operator can change a classification by re-running `classify`,
by `allocate` (business percentage), or `update`; can take a row out of scope
with `archive` / `stash` / `remove`; and can auto-classify by regex with
`ledger rule add` / `rule apply`. There is no dedicated reject/clear verb and
no LLM accept/confirm flow. `classify --reaffirm` only bypasses the
field-identical no-op guard — it is not an LLM-accept gesture.
`ClassificationHistoryEntry.provenance` is a reserved extension point an LLM
path could record into.

### Implication

Closing the gap is a code/product effort, not a documentation task. The staged
remediation: first wire the existing classifier into an operator
suggest -> review -> confirm / override / reject loop persisting `llm:`
provenance (non-regulated dimensions: business/personal plus expense
category); then, under a separate legally-grounded decision, extend the
response schema and prompt to the regulated IVA/IRPF/base dimensions and feed
evidence for base/IVA separation.
