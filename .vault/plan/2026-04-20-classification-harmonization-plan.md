---
tags:
  - "#plan"
  - "#classification-harmonization"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-20-classification-harmonization-adr]]"
  - "[[2026-04-20-classification-harmonization-research]]"
---

> **PRESERVATION NOTE (apex-PM sweep, 2026-04-27):** This plan was
> originally drafted in worktree `feature-255-vat-classification` on
> 2026-04-20, paired with the harmonization research + ADR for issue
> #255 (OPEN). Preserved on main 2026-04-27. When #255 implementation
> begins, proceed against this phased plan (Phase 1 closure of #236 is
> the gating dependency).

# `classification-harmonization` `blocked-groundwork` plan

Prepare the enlarged `#255` scope as a classification-pipeline harmonization
entry point without forcing runtime implementation before the unstable
provenance / confidence contract from `#236` lands.

## Proposed Changes

This plan reframes the next implementation cycle around one shared financial
classification backend. It does not execute the runtime restructure in this
blocked phase. Instead, it locks the work into ordered phases so that when
`#236` merges the repo can move directly into implementation without reopening
design.

The planned implementation must cover:

- transaction business / personal / mixed classification;
- spending-category assignment;
- personal income / expense classification surfaces where the pipeline must
  distinguish deductible business activity from non-business personal activity;
- VAT classification for invoice-backed and ad-hoc criteria;
- one decision-provenance contract shared by manual CLI and agentic / LLM
  callers.

## Tasks

- Phase 1: blocker closure and contract alignment
  1. Land `#236` on `main` and rebase the harmonization branch onto that
     contract.
  1. Audit `Transaction`, classification-history records, and any new
     `DecisionProvenance` types to confirm the final field names, validator
     rules, and backwards-compatibility constraints.
  1. Refresh the stale journey / coverage references so the implementation
     phase works from the actual repo state, not from pre-merge assumptions.

- Phase 2: shared backend extraction
  1. Introduce a common financial-classification decision layer that can
     represent manual, rule, fallback, and future LLM outcomes.
  1. Separate criteria normalization from catalogue persistence so VAT and
     category decisions are computed before they are written.
  1. Define the application boundary for transactions and invoices separately
     while keeping the decision contract shared.

- Phase 3: manual CLI harmonization
  1. Extend the transaction CLI so manual classification is expressed through
     the shared decision backend instead of bespoke argument-to-service wiring.
  1. Add `aeat vat classify` on top of the normalized VAT criteria path with
     human-readable insufficient-criteria errors.
  1. Add invoice-facing classification surfaces only where `#254` has made
     invoice persistence inputs available on `main`.

- Phase 4: invoice and VAT persistence integration
  1. Persist invoice-level VAT verdict fields and rule-fired metadata through
     dedicated invoice services.
  1. Support ad-hoc VAT classification and `--from-invoice` through the same
     backend so both routes emit identical verdict payloads.
  1. Ensure invoice show / list surfaces can render the persisted VAT verdict
     without bypassing the public service layer.

- Phase 5: agentic / LLM track enablement
  1. Define how rule-based and LLM-based classifiers call the shared backend
     and emit the same provenance / confidence objects as manual decisions.
  1. Keep review-queue semantics backend-driven so low-confidence or
     insufficient-criteria results are visible without CLI-specific hacks.
  1. Avoid introducing a second persistence contract for agentic workflows.

- Phase 6: verification and regression audit
  1. Add representative unit tests for the manual decision path, VAT rule
     firing, invoice persistence integration, and ambiguity handling.
  1. Add regression tests that prove transaction and invoice decisions serialize
     with the same provenance semantics.
  1. Re-run the Kent data-prep capability checks against the changed surfaces
     and update the coverage matrices to match the shipped behavior.

## Parallelization

This work should remain mostly serialized until Phase 2 is complete.

- Safe parallelism during the blocked phase: documentation refresh, issue / PR
  audit, and narrow code-reading passes.
- Risky parallelism before Phase 2 finishes: any independent edits to
  `transactions`, `invoices`, and VAT CLI surfaces, because they all need the
  same final decision contract.
- Once the shared backend is in place, transaction CLI and invoice / VAT
  persistence wiring can be split into parallel slices if they keep disjoint
  write sets.

## Verification

Mission success for the eventual implementation cycle is:

- the repo exposes one coherent shared classification backend rather than
  separate transaction-only and VAT-only write paths;
- manual CLI and agentic / LLM callers persist the same provenance /
  confidence semantics;
- VAT classification produces deterministic verdicts for representative rules
  and fails with human-readable guidance when criteria are incomplete;
- invoice-backed VAT classification and ad-hoc VAT classification agree when
  fed equivalent facts;
- updated coverage matrices and audit notes describe the shipped behavior
  truthfully.

For this blocked groundwork phase, success is narrower:

- research, ADR, and plan exist and are internally consistent;
- the docs name `#236` as the active blocker, `#253` as already merged on
  2026-04-18, and `#254` as the remaining invoice-ingestion dependency;
- no premature runtime code is added on top of an unstable backend seam.
