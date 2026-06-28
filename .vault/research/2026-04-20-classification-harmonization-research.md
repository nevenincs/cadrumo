---
tags:
  - "#research"
  - "#classification-harmonization"
date: "2026-04-20"
modified: '2026-04-20'
related:
  - "[[2026-04-18-category-assignment-cli-adr]]"
  - "[[2026-04-18-unclassified-state-adr]]"
---

> **PRESERVATION NOTE (apex-PM sweep, 2026-04-27):** This document was
> originally drafted in worktree `feature-255-vat-classification` on
> 2026-04-20 as part of the vaultspec triad for issue #255 (OPEN).
> Preserved on main 2026-04-27 so the design rationale survives if the
> worktree is rebased or retired. Status quo on main: issue #255
> remains open; this triad reflects the current documented intent
> (harmonization umbrella) — proceed accordingly when implementing.

# `classification-harmonization` research: `issue-255 expansion across the full classification pipeline`

This research bounds the expanded `#255` mandate after the issue was re-scoped
from VAT CLI wiring to full classification-pipeline harmonization. The goal of
this pass is not to force implementation before unstable dependencies land; it
is to identify the real seam lines, name the current blockers precisely, and
prepare a coherent architectural path for the shared backend that both manual
CLI and agentic / LLM-assisted classification flows will consume.

## Task bounds

- Topic: harmonize the financial classification backend so business
  classification, spending-category assignment, personal-income / expense
  classification, and VAT treatment can share one decision surface.
- Audit surface: `src/aeat/domain/financial/transactions`, `src/aeat/domain/financial/invoices`,
  `src/aeat/domain/financial/vat`, `src/aeat/domain/financial/categories`,
  `src/aeat/entrypoints/cli/financial/txs.py`, `src/aeat/entrypoints/cli/financial/invoices.py`,
  `src/aeat/entrypoints/cli/vat.py`, the current coverage matrices, and GitHub issues /
  PRs `#236`, `#253`, `#254`, `#255`.
- Rewrite scope: groundwork artifacts only for this blocked phase. No runtime
  code is changed until the unstable decision-provenance contract is settled.

## Findings

### 1. The shared backend does not exist yet; classification is split across three incompatible surfaces

- Transaction classification is stored on `Transaction` via
  `business_classification`, `business_pct`, `category_id`, `classified_by`,
  `classification_reason`, and `classification_history`.
- Invoice persistence is structurally separate. `Invoice` and `InvoiceLine`
  currently expose no VAT verdict fields such as `vat_category`,
  `vat_rule_fired`, decision provenance, or confidence.
- VAT classification is a pure engine in `aeat.domain.financial.vat.classify_vat`
  driven by `VATClassificationCriteria`, but it is not wired into invoice
  persistence or the mutable catalogue services.

### 2. `#253` is no longer the blocker; it already merged on 2026-04-18

- GitHub issue `#253` is closed as completed.
- PR `#288` (`feat(financial): Kent can assign spending category and reason via CLI (#253)`)
  merged into `main` on 2026-04-18.
- The live repo already reflects that merge: `aeat financial txs classify`
  accepts `--category` and writes `category_id`, while `set_classification`
  persists both `category_id` and `notes`.

### 3. The unstable seam is `#236`, not `#253`

- GitHub issue `#236` is still open as of 2026-04-20.
- PR `#250` (`feat(financial): decision provenance + confidence scoring (#236)`)
  is open and not yet merged.
- The current transaction model deliberately carries placeholders in
  `ClassificationHistoryEntry` (`confidence`, `provenance`) so that `#236`
  can land later without a schema break.
- The current code therefore encodes an intentionally incomplete contract:
  transaction history knows it will gain real decision provenance, but the
  public classification services and sibling catalogue models have not yet
  been reshaped around that contract.

### 4. The current CLI surfaces reinforce the split instead of hiding it

- `aeat financial txs` is the only writable classification surface on `main`.
  It can set manual business classification, `business_pct`, category, and
  free-text reason.
- `aeat financial invoices` is a reconciliation / listing surface only:
  `list`, `show`, `link`, `reconcile`, `verify`, and `unmatched`. There is no
  invoice ingestion or classification command on this surface yet.
- `aeat vat` is read-only: `categories list`, `rates list`, `show`, `rule`,
  and `verify`. There is no `classify` command and therefore no way to invoke
  `classify_vat` from the CLI.

### 5. The current models do not support the enlarged pipeline scope cleanly

- `Transaction` is the only financial record with lifecycle-like decision
  state. It can represent manual overrides and append-only history, but it
  cannot yet express a first-class decision object shared by rule, manual,
  LLM, and VAT-specific outcomes.
- `InvoiceLine.category_id` exists, but `Invoice` itself has no top-level
  financial-classification or VAT-classification summary fields.
- The category catalogue already includes a `vat_hint`, but that hint is static
  metadata for category profiles. It is not a persisted runtime verdict and it
  cannot substitute for the VAT engine's rule-fired output.

### 6. The audit and coverage docs are now stale relative to merged work

- `docs/coverage/pipeline.md` still says confidence is entirely absent and
  treats T4 as "manual only" despite the open but not merged `#236` work.
- `docs/coverage/kent-capabilities.md` still marks manual classification reason
  capture as entirely unsupported even though `#253` merged the `--reason`
  surface on 2026-04-18.
- The data-prep journey audit correctly names the structural mismatch between
  data-model richness and CLI reach, but its DP6 wall is now historically
  resolved by PR `#288`.

### 7. The enlarged `#255` scope naturally decomposes into one shared decision library plus two orchestration tracks

- Manual track: explicit user-driven CLI commands that can classify or
  override transactions, invoices, and VAT treatment with human-readable
  validation failures.
- Agentic track: rule / LLM pipelines that emit the same typed decisions,
  confidence, and provenance records without inventing a second persistence
  contract.
- Both tracks need one shared backend that can:
  1. accept normalized classification criteria;
  2. emit typed decision records with provenance and confidence;
  3. apply those decisions consistently to transaction and invoice catalogues;
  4. surface review-required states without smuggling workflow logic into
     Typer commands.

### 8. The main blocker after `#236` will be invoice-ingestion ownership in `#254`

- `#255`'s original `--from-invoice` acceptance path depends on invoice
  ingestion and persistence work tracked by `#254`.
- That dependency is still real even after the scope expansion: the full
  classification backend can be prepared independently, but end-to-end invoice
  classification cannot be completed until invoice add / parse / persist flows
  exist on `main`.

## Recommendation

Treat the enlarged `#255` as a harmonization umbrella implemented in two
stages:

1. Block runtime restructuring on `#236` landing, because the decision
   provenance and confidence contract must be the shared foundation.
2. During the blocked phase, produce an ADR and plan that redefine `#255`
   around a shared classification-decision backend spanning transactions,
   invoices, VAT, and future agentic classifiers.
3. Once `#236` lands, implement the shared backend first, then wire the manual
   CLI track, then the agentic / LLM track, and only then complete
   invoice-driven VAT classification as `#254` makes invoice ingestion
   available.
