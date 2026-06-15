---
tags:
  - '#adr'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-14-llm-classification-workflow-audit]]"
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

# `llm-classification-workflow` adr: `Audit-trailed LLM review loop: explicit reject as the fourth decision terminal` | (**status:** `accepted`)

## Problem Statement

The LLM classification surface (categorise, classify, saturate IVA/base, read
evidence with on-host vision, recommend and action evidence-driven splits) is
production-complete and honesty-reviewed. The campaign-close audit
(`2026-06-14-llm-classification-workflow-audit`) found one deferred gap, F10: the
operator's *review loop* has three terminals — **review** (preview, persists
nothing), **approve** (`--apply`), and **update** (manual override) — but
**reject** is implicit. Declining a suggestion is "do nothing", which leaves no
audit record that the operator saw the model's proposal and judged it wrong. For
a filing-grade system used by a gestor reviewing many rows, "the model said X and
I rejected it because Y" is provenance worth keeping, and its absence is the last
hole in an otherwise-complete decision loop.

## Considerations

- A rejection is a *judgement about a proposal*, not a mutation of the
  transaction: the row stays genuinely unclassified (review status `pending`). So
  reject must NOT write a classification, a number, or a lifecycle change — only an
  audit event.
- To reject a *concrete* proposal honestly, the rejected suggestion must be
  captured. The cleanest capture is to run the suggestion at reject time (the same
  one model call the approve path makes) and record what was declined, rather than
  recording a bare "operator declined LLM" with no content.
- `cli-notices-are-the-only-diagnostic-channel`, `llm-selects-system-derives-tax-numbers`,
  and the on-host/cloud evidence-consent gates are all load-bearing and unchanged
  by a read-only audit event.
- Bucket events carry free-form `Mapping[str, str]` payloads and need only a new
  `BucketEventType` member; there is no exhaustiveness gate forcing downstream
  handling, so the addition is additive and low-risk.

## Constraints

- The transaction must remain unmutated and `review_status` must stay derived from
  `business_classification` (a rejected-but-unclassified row is correctly
  `pending` — it still needs a decision). Making `review_status` depend on reject
  events is explicitly out of scope (it would couple the projection to event
  history); a "declined" review filter is deferred.
- No new persisted proposal entity / review-queue table — the existing
  `ledger list --status pending` is the queue. Reject is an audit event, not a
  workflow object.
- Parent surfaces (suggest/saturate/auto-split, evidence dispatch) are stable and
  shipped; this layers on top.

## Implementation

**Decision: add an explicit, audit-trailed reject as the fourth decision terminal,
recorded as a new bucket event that captures the rejected suggestion plus the
operator's reason, mutating nothing.**

1. **Event (domain).** Add `BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED`
   (`"ledger.transaction.llm_suggestion.rejected"`), pinned by a catalogue test.

2. **Application.** `reject_llm_suggestion(...)` accepts the captured proposal
   (an `LLMClassificationSuggestion`, `LLMSaturatedSuggestion`, or `LLMSplitSuggestion`)
   plus an operator `reason`, loads the transaction (to validate it exists and is
   active), and emits the rejection event with payload {`classification` /
   `category` / `iva_category` (or `child_count` for a split), `provenance`,
   `confidence`, `reason`, `mutation_kind = "llm_suggestion_rejected"`}. It does
   NOT call `set_classification` or `update_manual_transaction_fields` — the
   catalogue is untouched. Returns a typed `LLMSuggestionRejectionResult`.

3. **CLI.** `classify <id> --llm <provider> [--read-evidence] [--saturate] --reject
   [--reason "..."]` and `classify <id> --read-evidence --auto-split --reject
   [--reason "..."]`. `--reject` is mutually exclusive with `--apply`; it runs the
   relevant suggestion (one model call), prints what is being rejected, and records
   the event. An `info` `Notice` confirms the rejection was logged and points at the
   manual-override next step.

4. **Surfacing.** The rejection rides `ledger history <id>` — the new event type is
   added to the history command's displayed-event allowlist
   (`_LEDGER_HISTORY_EVENT_TYPES`) so the operator sees the declined proposal,
   its provenance, and the reason in the audit trail. (A one-line "last LLM
   suggestion: rejected" hint on `ledger view` is a deferred nicety — `ledger view`
   does not read events today, and the history surface already carries the
   provenance.)

5. **The loop, documented.** review → approve (`--apply`) → reject (`--reject`,
   audit-trailed) → update (manual override) is documented in the how-to as one
   contract; each terminal is distinct and auditable.

## Rationale

The three existing terminals are real but the missing fourth made "I reviewed and
declined" invisible — the exact provenance a filing-grade, multi-row review needs.
Recording reject as a captured audit event (not a mutation) closes the loop without
inventing a proposal entity, without touching the classification write path, and
without coupling `review_status` to events. Running the suggestion at reject time
keeps the record honest (a concrete declined proposal, not a contentless decline),
at the same one-call cost as approve. Every existing invariant — no model number,
notice-channel diagnostics, evidence consent — is preserved because reject only
appends an event.

## Consequences

- The operator review loop is complete and fully auditable: every decision
  (approve, reject, override) leaves a typed trail; only "review" (preview) is
  intentionally trace-free because it changes nothing.
- A rejected row stays `pending` — correct, because it is still unclassified. A
  future "declined" review filter (exclude rows whose latest LLM decision is a
  rejection from the pending queue) is a clean follow-on but is deliberately not
  built here, to keep `review_status` a pure projection of classification.
- Reject costs one model call (it captures a concrete proposal). An operator who
  already previewed and simply wants to log a decline pays for one more call; this
  is the honest cost of recording *what* was rejected.
- Split rejection records the proposal shape (child count + reason) rather than per
  child; per-child reject provenance is unneeded since the whole split is declined
  as a unit.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
