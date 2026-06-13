---
tags:
  - "#adr"
  - "#classification-harmonization"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-20-classification-harmonization-research]]"
  - "[[2026-04-18-unclassified-state-adr]]"
  - "[[2026-04-18-category-assignment-cli-adr]]"
---

> **PRESERVATION NOTE (apex-PM sweep, 2026-04-27):** This ADR was
> originally drafted in worktree `feature-255-vat-classification` on
> 2026-04-20 as part of the vaultspec triad for issue #255 (OPEN).
> Preserved on main 2026-04-27. Status quo on main: issue #255 remains
> open; this ADR reflects the current documented intent (harmonization
> umbrella around #236 + #253 + #254). When #255 implementation begins,
> proceed against this ADR.

# `classification-harmonization` adr: `recast issue-255 as the shared financial classification backend` | (**status:** `accepted`)

## Problem Statement

Issue `#255` started as a narrow VAT CLI-wiring task, but the actual repo state
shows a broader problem: financial classification logic is fragmented across
manual transaction updates, read-only VAT metadata, and invoice records with no
runtime classification layer of their own. The project now needs one shared
backend that can support both of the intended execution tracks:

- manual classification through CLI workflows; and
- agentic / LLM-assisted classification pipelines.

Implementing VAT-only wiring directly on top of the current split would harden
an already temporary boundary and force later migrations once confidence and
decision provenance from `#236` land.

## Considerations

- `#253` already merged on 2026-04-18 and established manual category
  assignment on transactions. The repo can no longer assume that category
  assignment is "incoming" work.
- `#236` remains open on 2026-04-20 and introduces the real contract that a
  shared backend must consume: typed decision provenance plus confidence.
- `#254` still owns invoice ingestion. The full `--from-invoice` VAT path
  cannot close until invoice creation / parsing is available on `main`.
- Kent's journey requires a single story: classify income / expense nature,
  assign spending or income categories, determine deductible proportion where
  relevant, and determine VAT treatment where relevant.
- The existing `classified_by` contract on transactions is too narrow for the
  enlarged scope if invoices and VAT decisions must be first-class persisted
  outcomes instead of incidental CLI side effects.

## Constraints

- No runtime implementation in this blocked phase may assume the final `#236`
  payload shape before it merges.
- The public classification surface must stay Kent-first and human-readable.
  Ambiguous or incomplete inputs must fail with guidance, not with model-level
  tracebacks.
- The design must preserve the current immutable catalogue discipline:
  service helpers return fresh validated records and do not mutate in place.
- Invoice-driven VAT classification remains partially blocked on `#254`.

## Implementation

When the blocker clears, `#255` will no longer be implemented as "add one VAT
CLI command." It will introduce a shared financial classification backend with
these responsibilities:

1. Define a single typed decision object for financial classification outcomes.
   That object will be grounded on the `#236` provenance / confidence contract
   and will carry:
   - decision kind;
   - decided-by / reason / confidence provenance;
   - manual override semantics;
   - review-required or insufficient-criteria findings where no deterministic
     outcome can be produced.
2. Split domain application from CLI orchestration:
   - transaction services apply business / personal / mixed and category
     decisions;
   - invoice services apply invoice-level and VAT-level decisions;
   - VAT services remain the pure rule engine plus criteria normalization.
3. Add one normalization layer that can derive VAT criteria from either:
   - explicit ad-hoc CLI flags; or
   - persisted invoice data once `#254` lands.
4. Keep two orchestration tracks on top of the same backend:
   - manual CLI commands for Kent;
   - agentic / LLM pipelines that emit the same decision types.

This ADR therefore authorizes groundwork artifacts now and defers runtime code
until the `#236` contract is available on `main`.

## Rationale

This option matches the actual merge state and avoids a known trap:

- If VAT wiring lands first, the repo gets a second ad-hoc decision path before
  the shared provenance contract exists.
- If invoice persistence is extended first without a common decision model,
  transactions and invoices will diverge further in how manual overrides,
  reasons, and confidence are stored.
- By recasting `#255` as harmonization, the project can absorb `#236` once and
  implement one classification backend that both CLI and agentic flows share.

The repo's own audit trail already points here: Kent's data-prep journey shows
that the code "knows" categories, VAT, and proportionality, but the CLI cannot
apply them coherently. The correct repair is a shared backend, not another
point fix.

## Consequences

- Positive: the next implementation cycle will have a single target
  architecture for business classification, category assignment, personal
  income / expense treatment, and VAT classification.
- Positive: `#236` becomes an explicit architectural prerequisite instead of an
  implicit future migration risk.
- Positive: `#254` remains a clean dependency boundary for invoice-driven
  classification instead of being partially reimplemented inside `#255`.
- Negative: the original narrow `aeat vat classify` command is deferred until
  the shared backend work starts.
- Negative: coverage matrices and issue wording will need a follow-up refresh
  because the merged / open state has already drifted past the current docs.
