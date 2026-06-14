---
tags:
  - '#adr'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - "[[2026-06-14-llm-classification-workflow-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace llm-classification-workflow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `llm-classification-workflow` adr: `LLM classification workflow contract: split recommendation, evidence-driven auto-split, and the review loop` | (**status:** `accepted`)

## Problem Statement

The evidence-aware LLM classifier reads an attached invoice and classifies one
ledger transaction, and a complete evidence-driven split engine
(`suggest_evidence_split` / `apply_evidence_split`) already separates a multi-line
invoice into children each carrying an independent registry-derived taxable base
and IVA cuota. But the *workflow* around the read is under-defined (research F1–F4):
`classify` and `split` are disjoint verbs, the split proposer cannot return a
"no split warranted" verdict (F2), `classify --read-evidence` never signals that an
invoice is multi-component (F3), and the suggest → review → update → reject → approve
loop is real but implicit, spread across flags, and emits a free-text hint instead
of a typed `Notice` (F4). The operator expects the classifier to *recognise* a
multi-rate invoice and let them *action* the base/IVA-separating split, intelligently
and discoverably.

## Considerations

- The base/IVA separation is regulatory: a single bank charge that bundles a 21%
  line and a 10% line must split so each line's deductible IVA and base-rate expense
  file independently on Modelo 303 / Modelo 130. Flattening it to one IVA category
  under-/over-states deductible IVA.
- `llm-selects-system-derives-tax-numbers` is load-bearing: the model selects
  categories and a proportion; every euro amount and regulated number is derived
  from the parent gross and the registry rate. A recommendation or an auto-split must
  add no model-emitted number.
- `cli-notices-are-the-only-diagnostic-channel`: a "consider splitting" hint is a
  non-blocking advisory and MUST ride the typed `Notice` channel, not a bespoke
  result field or a free-text line.
- The on-host vision vs cloud-subprocess evidence dispatch and its consent gates
  (binding `2026-06-10-llm-evidence-classification-adr`) are unchanged; this ADR
  adds nothing that moves bytes off-host.

## Constraints

- Relaxing `LLMSplitResponse` to accept a single child must not let
  `apply_evidence_split` / `split_transaction` attempt a degenerate 1-way split:
  the single-child case is a *verdict*, surfaced for review, never applied as a
  split.
- The `multiple_components` signal is a model judgement available only when evidence
  is actually read; with no evidence it stays `None` and no recommendation fires.
- No parent feature is frontier; this layers additively on the shipped split engine
  and the shipped evidence read. No new library.

## Implementation

**Decision: add a thin recommendation-and-auto-split layer over the existing split
engine, and document the four-action review loop as one contract. The model gains
exactly one new judgement (is this invoice multi-component?) and the split proposer
gains the ability to say "one line, no split". No regulated number becomes
model-emitted.**

1. **No-split verdict (domain).** `LLMSplitResponse` accepts **one or more**
   children (proportions still sum to ~1.0); a single child with proportion 1.0 is
   the "no split warranted" verdict. `build_split_prompt` instructs the model to
   return one child per distinct invoice line and exactly one child when the invoice
   is a single line/rate. `LLMSplitSuggestion` exposes a derived
   `recommends_split` (= more than one child).

2. **Multiplicity signal (domain).** `LLMClassificationResponse` gains
   `multiple_components: bool | None` (default `None`).
   `build_classification_prompt`, only when evidence is present, asks the model to
   set it true when the invoice carries multiple distinct rate/category lines. It is
   a boolean judgement, not an allow-list value, so the hallucination-containment
   parse is unaffected.

3. **Split recommendation (application + CLI).** The classification suggestion
   carries `multiple_components` through to the CLI. When true,
   `classify --read-evidence` emits an **`info`-severity `Notice`** whose
   `suggestion` is the exact runnable command
   (`aeat app ledger split --llm --read-evidence --apply --yes <id>`) and whose
   `context` records that the recommendation came from the evidence read. The
   free-text `llm_review_hint` is replaced by this typed notice on the LLM paths.

4. **Auto-split action (CLI).** `classify --read-evidence --auto-split` makes a
   single model call — the split proposer — and routes on its verdict. A
   multi-child verdict drives the evidence-split path (previewing children, or with
   `--apply` applying the base/IVA-separating split). A single-child "no split"
   verdict is classified in place: that lone child already carries the
   model-selected categories and the registry-derived base/IVA for the whole gross,
   so a dedicated `apply_evidence_classification` stamps them on the parent through
   the same single-writer the split apply uses per child — no second model call.
   `--auto-split` requires `--read-evidence` and is mutually exclusive with the
   manual override flags.

5. **The review loop, documented as one contract.** The four operator actions are
   named and bound to surfaces: **review** = the suggest preview (persists nothing);
   **approve** = `--apply`; **reject** = decline to apply (no write, no audit event,
   by design — a rejected suggestion never existed in the ledger); **update** = the
   fully-manual override path (`classify --classification … --category-id …`), which
   remains the explicit operator authority and is mutually exclusive with `--llm`.
   The how-to guide documents the loop; the conformance gate keeps the cited
   commands runnable.

## Rationale

The split engine, the per-child registry derivation, and the consent-gated evidence
read are all shipped and proven (research F1, F5); the only missing pieces are a
*judgement* (multi-component?) and a *route* (auto-split / recommend), both of which
are additive and preserve every existing invariant. Making the no-split case a
first-class verdict (F2) is what makes an auto-split trigger correct on the common
single-line invoice. Routing the recommendation through `Notice` keeps the diagnostic
channel uniform (`cli-notices-are-the-only-diagnostic-channel`). Keeping the manual
override as the "update" channel avoids inventing a parallel edit-the-suggestion
surface that would duplicate the existing classification write.

## Consequences

- The operator can now run one command (`classify --read-evidence --auto-split
  --apply`) and have a multi-rate invoice separated into independently-filable base
  and IVA children, or a single-line invoice cleanly classified — the model decides
  which. The base/IVA separation requested is delivered through the existing,
  tested derivation, not a new numeric path.
- The auto-split path costs exactly one model call: the split proposer's response
  is both the verdict and the per-line (or single-line) selection set, so no
  separate classify call is needed in either branch.
- A model that wrongly flags `multiple_components` only produces a *recommendation*;
  nothing is written until the operator approves, so a false positive is a dismissed
  notice, not a bad filing.
- Future work (not this ADR): an audit-trailed explicit reject verb and a
  review-queue surface for batch operators; the implicit reject is sufficient for the
  single-operator path today.

## Codification candidates

- **Rule slug:** `llm-split-recommendation-rides-the-notice-channel`.
  **Rule:** An LLM-derived "this transaction should be split" recommendation MUST be
  surfaced as a typed `info` `Notice` whose `suggestion` is the runnable split
  command, never as a bespoke result field or a free-text line, and an auto-split
  MUST add no model-emitted euro amount or regulated number (the registry derives
  every child's base and IVA). The `2026-06-14-llm-classification-workflow-audit`
  honesty review confirmed the surface shipped and the constraint holds, and
  resolved NOT to author a new rule: the recommendation-rides-the-`Notice`-channel
  half is already bound by `cli-notices-are-the-only-diagnostic-channel` and the
  no-model-emitted-number half by `aeat-calculation-grounding` /
  `llm-selects-system-derives-tax-numbers`. The auto-split surface is a worked
  example under those rules, not a third overlapping rule.
