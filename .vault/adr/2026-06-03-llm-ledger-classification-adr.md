---
tags:
  - '#adr'
  - '#llm-ledger-classification'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-llm-ledger-classification-research]]"
---



# `llm-ledger-classification` adr: `Wire LLM-assisted ledger classification into an operator suggest/confirm/reject loop (MVP)` | (**status:** `accepted`)

## Problem Statement

LLM-assisted transaction classification is intended to be a pivotal ledger
feature — the operator's heaviest task is classifying transactions. The
research investigation found the classifier is built but **unreachable**: a
mature `SubprocessLLMClassifier` (and a separate API `LLMClient`) exist with
prompts, providers, a hallucination guard, and tests, yet no CLI verb,
application service, or import hook ever calls them, and there is no operator
provider config. `aeat app ledger classify` is 100 percent manual. This ADR
decides the first stage: make the existing classifier reachable by an operator
through a safe suggest / review / confirm / override / reject loop. The
regulated tax-dimension extension is explicitly deferred (see Constraints).

## Considerations

- The operator must be able to (a) ask the LLM to classify a transaction,
  (b) review the suggestion before anything is persisted, (c) accept it,
  (d) override it with a manual decision, and (e) reject it (leave the row
  unchanged).
- The classifier already emits a non-regulated decision: `classification`
  (BUSINESS / PERSONAL / MIXED), `confidence`, `reason`, and an optional
  expense `category`. None of these are AEAT-calculated regulatory values, so
  this MVP can ship without legal-grounding work.
- Provenance must distinguish an LLM decision from a manual or rule decision.
  `Transaction.classified_by` already supports an override identifier, and the
  classifier exposes `decided_by` (e.g. `llm:<model>`);
  `ClassificationHistoryEntry.provenance` is a reserved slot for the confidence
  and reason.
- The subprocess backend needs a local `claude` / `gemini` / `codex` CLI on
  `PATH`; availability must be checked and reported, never assumed.
- The two roots of the CLI are fixed (`config`, `app`); the new surface lives
  under the existing `aeat app ledger` group.

## Constraints

- **Regulated dimensions are out of scope for this MVP.** The classifier does
  not produce `taxable_base`, `iva_rate`, `iva_amount`, `iva_category`,
  `irpf_category`, or the MIXED business percentage, and evidence-based
  base/IVA separation does not exist. Producing those via LLM is a regulated
  calculation requiring legal grounding (per the calculation-grounding and
  registry-legal-grounding rules) and a corpus to validate against; it is
  deferred to a separate, legally-grounded ADR. This MVP must not invent or
  persist any regulated tax value from an LLM.
- **Provider availability is a runtime dependency.** The subprocess backend
  requires an external CLI on `PATH`; the feature must degrade to a clear,
  instructive refusal when the chosen provider is unavailable, never a crash.
- **Hallucination containment is mandatory.** Only the existing
  allow-list-guarded `parse_response` path may map an LLM response to a
  classification/category; an out-of-allow-list value is rejected, never
  persisted.
- **Parent stability.** This builds only on the already-stable manual
  classify persistence path (`set_classification` / classified-by override)
  and the existing classifier engine; it adds no new persistent state machine.

## Implementation

A thin application use case sits between the CLI and the existing classifier:
given a transaction id and a provider, it loads the transaction, resolves the
classifier through the existing registry with the category-enabled prompt
spec, runs `classify`, and returns the typed suggestion (classification,
optional category, confidence, reason, and the `decided_by` provenance string)
**without persisting**. A separate apply path persists an accepted suggestion
through the existing manual-classification write, setting the classified-by
override to the classifier's `decided_by` and recording confidence and reason
in the classification-history provenance slot.

The operator surface extends `aeat app ledger classify` with a `--llm
<provider>` mode. Without `--apply`, it prints the suggestion for review and
persists nothing (this is the suggest step; rejecting is simply not applying).
With `--apply`, it persists the LLM decision with `llm:<model>` provenance.
Manual classification is unchanged and always wins: re-running `classify` with
an explicit `--classification` (and category) overrides any prior LLM decision
and stamps manual provenance. A provider-availability check (surfaced through
a status/listing the operator can run, and enforced at classify time) reports
which LLM providers are usable and refuses instructively when one is not.

Override and reject therefore reuse existing mechanics: override is the
existing manual `classify`; reject is declining `--apply` (or re-classifying
manually); the row is never mutated until an explicit apply or manual write.

## Rationale

The research found a roughly 80-percent-built, 0-percent-reachable feature.
Wiring the existing engine into the manual-classify persistence path is the
smallest change that delivers the operator's core ask (leverage + review +
accept + override + reject) and is shippable now because every dimension it
touches (business/personal, expense category) is non-regulated. Deferring the
regulated IVA/IRPF/base extension keeps this MVP free of legal-grounding risk
while the suggest/confirm/reject UX, provider plumbing, and `llm:` provenance
land first and become the foundation the grounded extension builds on.

## Consequences

- **Gain:** the pivotal feature becomes real — an operator can have the LLM
  classify a transaction, see why, and accept / override / reject it, with
  provenance recording that the decision came from a model.
- **Gain:** establishes the provider-availability, suggestion-preview, and
  `llm:` provenance plumbing the regulated extension will reuse.
- **Honest limitation:** the MVP only sets business/personal and expense
  category. The operator still enters `taxable_base` / IVA / IRPF by hand; the
  docs must say so plainly so no one believes the LLM fills the tax substrate.
- **Dependency surfaced:** value depends on a local provider CLI being
  installed; without one the feature refuses. Operators on the API client path
  remain unserved until a later increment wires it.
- **Pitfall to avoid:** scope creep into regulated derivation without
  grounding; the apply path must hard-refuse persisting any regulated tax value
  from the LLM in this stage.

## Codification candidates

- **Rule slug:** `llm-outputs-are-suggestions-not-authority`.
  **Rule:** An LLM-produced classification or value must be presented for
  operator review and persisted only on explicit apply, must carry `llm:`
  provenance distinct from manual and rule decisions, and must never originate
  a regulated AEAT tax value (rate, base, cuota) without separate legal
  grounding.


