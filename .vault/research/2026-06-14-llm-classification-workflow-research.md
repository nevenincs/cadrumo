---
tags:
  - '#research'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
related: []
---



# `llm-classification-workflow` research: `LLM classification workflow: review/approve/reject loop and evidence-driven auto-split`

The Stage-3 evidence-aware LLM classifier reads an attached invoice (text-layer
on a cloud subprocess, scan/image on an on-host vision model) and classifies one
ledger transaction. The live read is proven end to end. This research grounds the
next gap the operator surfaced: the *workflow* around the read is under-defined.
A multi-line invoice — one whose lines carry different IVA rates or expense
categories — should be **recognised** as multi-component and the operator should
be able to **action a split** that separates each line into its own child with an
independent taxable base and IVA cuota, so deductible IVA and base-rate expense
file independently. Today `classify` and `split` are disjoint verbs and the model
is never asked whether a split is warranted.

## Findings

### F1 — The evidence-driven split already exists end to end, but only as a separate verb

`suggest_evidence_split` → `apply_evidence_split` in
`src/aeat/application/ledger/_llm_classification.py` is a complete suggest → review
→ apply loop: it loads the parent, runs the `LLMSplitProposer` over the on-host
evidence (text or vision image), DERIVES each child's euro amount from the parent
gross and the child's proportion (summing exactly to the parent), and DERIVES each
child's `taxable_base` / `iva_rate` / `iva_amount` from the registry rate for the
model-selected `IvaCategory`. The apply path composes the single-writer
`split_transaction` then per-child `update_manual_transaction_fields`, stamping the
`llm:<model>` provenance and the parent invoice's evidence link. The CLI exposes
this as `aeat app ledger split --llm --read-evidence [--apply --yes]`
(`_ledger_split_llm` in `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`). The
base/IVA separation the operator asked for is therefore already implemented — it is
the *discoverability and intelligence* around it that is missing.

### F2 — `split --llm` forces ≥2 children; the model cannot return a "no split" verdict

`LLMSplitResponse._check_children` in `src/aeat/domain/transactions/_llm.py` raises
when fewer than two children are proposed, and `build_split_prompt` instructs the
model to "divide this transaction into TWO OR MORE children". A single-line invoice
run through `split --llm` is therefore coerced into ≥2 artificial children. There is
no path for the model to read the invoice and answer "this is a single line, no
split warranted". This blocks any auto-split trigger: an auto-split that always
splits is wrong on the common single-line case.

### F3 — `classify --read-evidence` never signals that the invoice is multi-component

`LLMClassificationResponse` (`src/aeat/domain/transactions/_llm.py`) carries
`classification` / `category` / `iva_category` / `business_pct` but no
multiplicity signal, and `build_classification_prompt` never asks the model whether
the invoice contains multiple distinct rate/category lines. So
`classify --read-evidence` picks ONE classification and one IVA category for the
whole gross and silently flattens a multi-rate invoice. The operator is given no
recommendation to split, and must independently know to run `split --llm`.

### F4 — The review/update/reject/approve loop is real but implicit and undocumented

The suggest step prints the suggestion and persists nothing
(`LedgerClassifyLlmSuggestResult`); `--apply` persists it; "reject" is simply not
applying. "Update" (correcting a category the model got wrong) is served by the
fully-manual override path (`classify --classification X --category-id Y …`), which
is mutually exclusive with `--llm`. These four operator actions exist but are
spread across flags and modes with no single documented contract, and the
suggest preview emits a free-text `llm_review_hint` line rather than a typed
`Notice`. Per `cli-notices-are-the-only-diagnostic-channel`, a recommendation to
split belongs on the typed `Notice` channel, not a bespoke result field.

### F5 — Numbers stay system-derived; the model selects, the registry computes

Across `classify --saturate` and `split --llm`, the model emits only a
`proportion` and allow-list-guarded category/IVA selections; the euro amounts and
the regulated `taxable_base` / `iva_rate` / `iva_amount` are derived by
`derive_child_amounts` + `split_gross_at_rate` / `resolve_category_rate` against
the registry (`llm-selects-system-derives-tax-numbers`). Any new auto-split path
MUST preserve this: a split recommendation and an auto-split action add no
model-emitted number; they only re-route which derivation runs.

## Implications for the decision

The completion work is a thin, additive layer over the existing split engine:
(1) let the split proposer return a single-child "no split" verdict so multiplicity
is a model judgement, not a forced assumption; (2) let `classify --read-evidence`
carry a `multiple_components` flag and surface a typed split-recommendation
`Notice`; (3) add `classify --read-evidence --auto-split` that runs the split
proposer and either applies the multi-child split or falls back to single-transaction
classification when no split is warranted; (4) document the suggest → review →
update (manual override) → reject (don't apply) → approve (`--apply`) loop as one
contract. No regulated number becomes model-emitted.
