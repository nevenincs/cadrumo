---
tags:
  - "#research"
  - "#unclassified-state"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# `unclassified-state` research: `disambiguate-unclassified`

## Scope

Issue `#237` requires the pipeline to stop collapsing four distinct states into the single `BusinessClassification.UNCLASSIFIED` value, and to preserve a `ClassificationHistory` chain so Kent can inspect every decision ever applied to a transaction.

EPIC context is `#204` (umbrella) and sibling sub-EPICs `#236` (confidence on decisions) and `#238` (findings beyond drafts).

## Current codebase inventory

### `BusinessClassification` definition and default

- `src/aeat/domain/financial/transactions/_enums.py:16-22` — `StrEnum` with `BUSINESS`, `PERSONAL`, `MIXED`, `UNCLASSIFIED`.
- `src/aeat/domain/financial/transactions/_models.py:71` — `Transaction.business_classification: BusinessClassification = BusinessClassification.UNCLASSIFIED`.
- `src/aeat/domain/financial/transactions/_models.py:152-163` — `_validate_business_pct` couples `MIXED` to `business_pct ∈ [0,1]`; every non-`MIXED` state enforces `business_pct is None`.

### Classification write-paths

- `src/aeat/domain/financial/transactions/_service.py:117-152` — `set_classification` mutates one transaction into a fresh catalogue entry, stamping `classified_at = datetime.now(UTC)` and `classified_by ∈ {"auto", "manual", "rule:<id>"}`.
- `src/aeat/entrypoints/cli/financial/txs.py:80-120` — `aeat financial txs classify <tx> --as <STATE> --pct 0.5` is the only manual surface; it calls `set_classification` with `classified_by="manual"`.
- No automatic T4-classify pipeline exists on `main`. Every classification today is either the catalogue default (`UNCLASSIFIED`) or an explicit manual write.

### Read-paths / filters

- `src/aeat/entrypoints/cli/financial/txs.py:30-64` — `aeat financial txs list --unclassified` filters to `business_classification is UNCLASSIFIED`.
- `src/aeat/entrypoints/cli/financial/txs.py:67-77` — `aeat financial txs show <tx>` dumps the full transaction JSON.

### Tests that depend on `UNCLASSIFIED`

- `src/aeat/domain/financial/transactions/test_cli.py:36` — default factory classification.
- `src/aeat/domain/financial/transactions/test_cli.py:115` — asserts `payload["business_classification"] == "UNCLASSIFIED"`.
- `src/aeat/domain/financial/transactions/test_catalogue.py:56, 129` — factory default and `set_classification` before-state assertion.

### Documentation

- `docs/coverage/pipeline.md:21-23` — "Classification history (versioned): ❌ — #237" and "`PROCESSED_UNCLASSIFIED` state distinct from `NOT_YET_PROCESSED`: ❌ — #237".

### Non-conflicting occurrences

The inbox notification classifier (`src/aeat/inbox/test_classifier.py`) uses the word `UNCLASSIFIED` in an unrelated fallback test helper. Out of scope.

## Cross-EPIC alignment

- `#236` (confidence) will add a `DecisionProvenance` record carrying `decided_by`, `reason`, and `confidence`. It does not touch the state enum. The new state axis (#237) and the confidence axis (#236) are orthogonal; both can be assigned to the same transaction.
- `#204` C14j mandates "ClassificationHistory chain — append-only tuple; every re-classification appends". Issue `#237` is scoped to ship this chain with the existing `classified_by` / `classified_at` provenance; once `#236` lands, new entries will embed `DecisionProvenance` directly. No history field is rewritten.
- `#204` C14i mandates a `--state <state>` filter on `aeat financial txs list`. Issue `#237` adds this filter. The legacy `--unclassified` flag should remain functional (mapped to `PROCESSED_UNCLASSIFIED` per the Kent success moment) during a deprecation window, but be marked hidden in help.

## Migration surface

- On-disk catalogue JSON currently stores `"UNCLASSIFIED"`. Any pre-existing Kent catalogue must continue to load after the split.
- The issue mandates: legacy `UNCLASSIFIED` aliases to `NOT_YET_PROCESSED` with a deprecation window. No destructive rename.
- The loader must normalise legacy strings before pydantic validation rejects them. The normaliser belongs in `Transaction._enforce_derived_transaction_id` (already coerces strings).
- Out-of-scope for this PR: a formal ADR-backed SQLite migration (no SQLite store for transactions exists yet). Catalogue persistence is JSON-only (`_service.py:21-43`). The migration strategy is therefore a transparent loader-side alias.

## Kent-observable acceptance

Per `#237` body:
- `aeat financial txs list --state PROCESSED_UNCLASSIFIED` shows only rows the pipeline saw and could not classify.
- `aeat financial txs list --state NOT_YET_PROCESSED` shows rows awaiting first pass (the catalogue default).
- `aeat review history <tx-id>` prints the chain — first decision preserved, every re-classification appended.
- Re-classifying a transaction does not destroy prior decisions.

## Open design questions

1. **Where does `aeat review` live?** There is no `review` top-level app yet; `#204` C4l sketches a future unified review queue. For `#237` the minimal ship is a new `src/aeat/entrypoints/cli/review/` subpackage that hosts `history <tx-id>` today and receives `queue` / `approve` in a follow-up PR.
2. **ClassificationHistory location.** The chain can be stored either on `Transaction` (inline) or out-of-band. Inline keeps `Transaction` self-contained and round-trips cleanly through `TransactionCatalogue` JSON. Out-of-band mirrors the future `var/decisions/YYYY-MM.jsonl` audit log (EPIC C14d). Inline is chosen for `#237`; the JSONL sink is `#204`-C14d scope.
3. **Legacy alias expiry.** No fixed deprecation cut-off is declared by `#237`. The ADR should capture a soft deadline anchored to milestone `0.2.0` ("Kent can verify his filings") so the alias dies with the next catalogue-schema bump.

## Closing

The state split is mechanically small (one enum, one default, one filter, one history field, one CLI command, two test factories). The discipline is all in (a) legacy alias correctness, (b) preserving immutability semantics when appending to the history tuple, and (c) coexisting with `#236` without preempting it.
