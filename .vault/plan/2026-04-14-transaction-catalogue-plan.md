---
tags:
  - "#plan"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-transaction-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-13-p2a-financial-provider-plan]]"
---

# `transaction-catalogue` `phase-1` plan

Deliver issue `#74` as the immutable transaction wrapper and catalogue layer at the T1/T2 seam: new `aeat.domain.financial.transactions` models and helpers, catalogue persistence, `aeat financial txs` CLI commands, additive settings wiring, colocated tests, and mandatory verification/review artefacts.

## Proposed Changes

- Create the `aeat.domain.financial.transactions` subpackage with strict enums, models, errors, persistence helpers, internal typing stubs, and a single public API surface.
- Implement deterministic transaction ID generation from the merged T1 `RawTransaction` shape while preserving the wrapped raw record verbatim.
- Add immutable catalogue operations for lookup, invoice linking, and manual/automatic classification updates.
- Add JSON persistence with atomic writes and a configured default storage directory.
- Extend the existing `aeat financial` CLI with `txs list`, `txs show`, and `txs classify`.
- Add colocated unit tests for hashing, validation, immutable-return semantics, persistence round-trip, and CLI smoke coverage.

## Tasks

- `Phase 1: establish the transaction package surface`
  1. Create `aeat.domain.financial.transactions` with public `__init__.py` and private underscore modules.
  1. Define enums, errors, `Transaction`, `TransactionCatalogue`, and internal `Protocol` stubs.
  1. Implement deterministic transaction ID helpers and catalogue constructors that reject duplicate logical IDs.
- `Phase 2: add persistence and immutable service functions`
  1. Implement catalogue load/save/find helpers with atomic one-file JSON persistence.
  1. Implement immutable `link_invoice` and `set_classification` operations with strict validation of `business_pct` and `classified_by`.
- `Phase 3: wire settings and CLI`
  1. Add `aeat_financial_txs_dir` to `Settings` and align `env/.env.example` plus config tests.
  1. Extend `aeat financial` with a nested `txs` Typer app and the list/show/classify commands.
- `Phase 4: verify and document execution`
  1. Add colocated `@pytest.mark.unit` tests for the new package and CLI.
  1. Run `just lint`, `just typecheck`, `just test`, and `just hooks`, fixing root causes until green.
  1. Write exec records and the mandatory audit, address any review findings, then prepare the final commit and PR body without pushing.

## Parallelization

This work is best executed sequentially because the package surface, persistence helpers, CLI wiring, and tests all share the same small set of models and invariants. The only safe overlap is documentation capture versus command execution, which can be handled incrementally as each implementation phase lands.

## Verification

- `Transaction` and `TransactionCatalogue` remain strict pydantic v2 boundaries and round-trip through `model_dump_json` / `model_validate_json`.
- `transaction_id` generation is deterministic for the same upstream raw tuple and produces collision-resistant SHA-256 identifiers.
- The wrapped `raw` object stays unchanged through every catalogue operation; update helpers return fresh catalogue instances instead of mutating in place.
- `business_pct` is rejected unless classification is `MIXED`, and accepted only within inclusive `0..1` when `MIXED`.
- `classified_by` accepts only `"auto"`, `"manual"`, or `"rule:<rule-id>"`.
- Persistence uses a single JSON file with atomic replacement and round-trips cleanly.
- `aeat financial txs list`, `show`, and `classify` are reachable from the root CLI and behave correctly in smoke tests.
- `just lint && just typecheck && just test && just hooks` pass on Windows for the final tree.

## Explicit Plan Review

- **Scope check against issue `#74`:** The plan covers the new transaction subpackage, persistence, CLI, settings, Protocol stubs, and colocated tests, and excludes submission writes, provider ingest changes, invoice/tax-category implementations, VAT logic, and modelo catalogue work.
- **TDP check against issue `#104`:** The plan keeps the work at the T1/T2 seam, preserves raw provenance verbatim, and avoids reaching into T3/T4 classification-rule ownership beyond the data slots this issue explicitly owns.
- **Convention check against active repo instructions:** The plan stays inside `src/aeat/`, uses strict pydantic v2, `StrEnum`, pytest-only tests, additive settings changes, and the canonical `AEAT_LIVE_TESTS_ENABLED` contract.
- **Sibling-surface check:** The plan avoids `src/aeat/adapters/outbound/aeat/export/`, avoids `src/aeat/domain/modelos/`, imports `RawTransaction` from `aeat.domain.financial.providers`, and keeps invoice/category references as internal typing-only stubs.
- **Repository policy check:** No GitHub Actions work is introduced; local gates remain authoritative.
- **`CLAUDE.md` check:** No `CLAUDE.md` file exists in this worktree. The review was therefore performed against the active `AGENTS.md`, vaultspec rules, the issue set named by the user, and the existing codebase conventions.
- **Review outcome:** Approved for execution under the user’s explicit instruction to run the full pipeline without pausing for plan approval.
