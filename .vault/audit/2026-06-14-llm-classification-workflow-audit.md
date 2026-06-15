---
tags:
  - '#audit'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-06-14-llm-classification-workflow-adr]]"
---



# `llm-classification-workflow` audit: `Campaign-close honesty review: split recommendation and auto-split`

## Scope

Fresh-context honesty review of the `llm-classification-workflow` campaign close
(per `aeat-campaign-close-honesty-review`), conducted by an independent
code-reviewer persona against the ADR's claims and the shipped code at HEAD.
Audited surface: feature commit `577c9e1bd` plus the size-budget refactor
`bd04d9248` — the domain no-split verdict + `multiple_components` signal, the
application `apply_evidence_classification` / `apply_evidence_split` routing, and
the CLI split-recommendation `Notice` + `--auto-split` dispatch.

## Findings

Overall verdict: **PASS** — no CRITICAL or HIGH issues; the shipped code
faithfully implements the ADR. The invariant claims all held under inspection.

### CONFIRMED CLEAN (claims that verified)

- **Invariant integrity** — no path lets the LLM emit a persisted euro amount or
  regulated number. Both the multi-child split and the new in-place
  `apply_evidence_classification` take every `taxable_base` / `iva_rate` /
  `iva_amount` from the registry-derived child substrate
  (`resolve_category_rate` + `split_gross_at_rate`); `LLMSplitChild`
  structurally refuses numeric fields. The `gross == taxable_base + iva_amount`
  invariant is enforced on the in-place write and asserted.
- **No-split routing** — `apply_evidence_split` refuses a single-child verdict,
  `apply_evidence_classification` refuses a multi-child one; both tested.
  `derive_child_amounts([1.0])` returns the whole gross; the manual
  `split_transaction` two-children floor is unaffected.
- **Notice channel** — the recommendation is a typed `info` `Notice`, not a
  bespoke result field, on both stage-1 and saturate previews; the text line
  rebuilds from the same notice so JSON and text cannot drift.
- **Consent/evidence gates** — `--auto-split` threads `evidence_acknowledged`
  through the existing consent gate, moves no bytes off-host, and leaves the
  on-host-vision vs cloud-subprocess dispatch untouched.
- **Provenance** — the in-place write stamps `classified_by = llm:<model>` and
  emits a real `LEDGER_TRANSACTION_CLASSIFIED` event.
- **One model call** — `dispatch_autosplit` calls `suggest_evidence_split` once;
  neither apply branch makes a second model call.
- **Test honesty** — real persistence, DI proposers, no mocks/xfail; asserted
  numbers are registry-derived reconstitutions, not formula outputs under test.
- **Plan/exec honesty** — all six exec records match shipped surfaces; no step
  checked without code.

### CLOSED THIS PASS (coverage + hygiene gaps surfaced and fixed)

- **F1 (MEDIUM) — `multiple_components` prompt-gating untested.** The field is
  correctly asked for only when evidence is read, but no test asserted it. Closed:
  added `test_multiple_components_asked_only_when_evidence_present`.
- **F2 (MEDIUM) — `multiple_components` parse round-trip untested.** Closed: added
  `test_multiple_components_survives_the_allow_list_parse` (flag true round-trips;
  absent → `None`).
- **F12 (LOW) — ADR duplicated `## Codification candidates` heading.** Closed:
  removed the empty scaffold duplicate; the real candidate remains.

### DEFERRED (tracked follow-up, not a defect)

- **F10 (LOW) — no audit record of a *rejected* LLM suggestion.** "Reject =
  decline to apply" persists nothing, so there is no "operator reviewed and
  declined" provenance. Acceptable for the single-operator path today; the ADR
  already defers an audit-trailed explicit-reject verb and a batch review-queue
  for gestor/batch operators. No data-integrity gap. Carry forward to a future
  review-loop campaign.

## Recommendations

- The closed coverage gaps (F1, F2) and the ADR hygiene fix (F12) land in this
  pass; no REVISION was required.
- Promote the `llm-split-recommendation-rides-the-notice-channel` candidate now
  that the surface has shipped and this review confirmed the constraint holds.
- Track F10 as a deferred follow-up bound to the future LLM review-loop campaign
  (explicit reject verb + batch review queue); do not let it block this close.

## Codification candidates


**None — the candidate is already covered by two existing rules; a new rule would
fragment the discipline.** The ADR's `llm-split-recommendation-rides-the-notice-channel`
candidate decomposes into two constraints that established project rules already
bind: the recommendation-rides-the-`Notice`-channel half is exactly
`cli-notices-are-the-only-diagnostic-channel` (a recommendation MUST be a typed
`Notice`, never a bespoke result field), and the no-model-emitted-number half is
the same `llm-selects-system-derives-tax-numbers` principle that
`aeat-calculation-grounding` and the registry-derivation discipline already
enforce across the calculate/saturate/split surfaces. Per the `vaultspec-codify`
guidance ("if an existing rule partially covers the intent, edit it rather than
producing a near-duplicate"), the auto-split surface is best recorded as a worked
example under those rules rather than promoted as a third overlapping rule. No new
rule authored.
