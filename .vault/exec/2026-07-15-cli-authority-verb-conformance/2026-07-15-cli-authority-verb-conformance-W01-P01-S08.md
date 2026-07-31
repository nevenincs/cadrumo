---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:37c9be6c2f70e3b8891c170d8fcaa3490bff47eaa1c4fc3635ef0569e46b9cd7'
step_id: 'S08'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Exercise M210 aggregation through the real injected transaction repository

## Scope

- `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`

## Description

- Ground the Step with the exact semantic query `vaultspec-rag search "M210 injected repository distinct ambient store source mesh calculation test" --type code --port 8766` after the supervised current-worktree index refresh.
- Trace `_resolve_bucket_source_mesh`, `_MemoizedTransactionCatalogueRepository`, `LedgerIrnrIncomeAggregationSourceResolver`, `aggregate_irnr_income_ledger_from_repositories`, the concrete transaction repository, and the real encrypted-storage helpers with exact source searches.
- Inventory every existing M210 public-calculation test and confirm none distinguishes the injected object store from ambient same-bucket storage.
- Add one focused public-path scenario with distinct ambient and injected real encrypted SQL object stores under the same active bucket session.
- Seed the qualifying M210 transaction only through the injected `TransactionCatalogueRepository` and keep the ambient transaction catalogue empty.
- Assert the injected gross value, source transaction id, and persisted provenance flow through the public bucket-calculation path.
- Run focused Ruff, the new test node alone, and the complete serial M210, memoized-repository, and resolver-enrollment lane.

## Outcome

The prior public M210 scenario supplied an injected repository, but that repository and ambient construction resolved to the same active secure-object store. It therefore stayed green if `_resolve_bucket_source_mesh` silently discarded injection and constructed `TransactionCatalogueRepository(bucket_id=...)` from ambient state.

The new scenario creates a second SQLite engine with production `create_engine_from_settings`, materialises the real ORM schema, and binds a real session-gated `SecureObjectRepository` to it. The ambient work-unit, profile, calculation, event, and empty transaction repositories remain on the runtime store for the same bucket id. Only the injected store receives the qualifying transaction. The public calculation returns `1234.56`, the injected transaction id, and `transaction:<id>` provenance while the ambient transaction catalogue remains empty.

This is mutation-sensitive without duplicating aggregation logic: replacing the source mesh's injected-repository choice with ambient construction produces no M210 observation, so all three result assertions fail. Existing tests continue to own classification, exclusion, evidence, staleness, verification, and source-mode breadth; this Step adds only the missing composition-root distinction.

The refreshed semantic result returned live `src/cadrumo` sections for the IRNR Protocol loader and resolver. Exact searches then confirmed the sole public choice point in `_resolve_bucket_source_mesh`, the shared memoized wrapper, the required resolver constructor, the Protocol-only repository loader, the concrete repository's explicit `objects` seam, and the absence of another distinct-store M210 test. The target contains no fake, mock, stub, monkeypatch, test patch, skip, or xfail pattern; `ManualLedgerTransactionPatch` is the production domain mutation command and is unrelated to test patching.

Verification passed:

- `uv run --no-sync ruff check src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py` reported `All checks passed!`.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py::test_bucket_calculation_uses_injected_transaction_store_over_distinct_ambient_store -vv` reported `1 passed in 72.44s`.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py src/cadrumo/application/modelo/tests/test_memoized_transaction_catalogue_repository.py src/cadrumo/application/aggregation/tests/test_source_resolver_enrollment.py -vv` reported `12 passed in 65.20s`.
- `vaultspec-core vault plan check` reported no findings after closing only S08 through the canonical plan command.
- `vaultspec-core vault check adr-status` and `vaultspec-core vault check placeholders` reported clean.
- `vaultspec-core vault check schema` reported only the unrelated older `2026-07-14-honest-all-green-plan.md` missing-research warning.
- `vaultspec-core vault check annotations` reported clean after removing the S08 scaffold hints and the plan template's `LINK RULES` hint reinserted by Step serialization, without changing plan structure.
- Feature-index regeneration succeeded and included this execution record; its repository-wide historical stem-collision warnings are unrelated to S08.

## Notes

The initial mandatory query reached the resident service but returned HTTP 500 because managed Qdrant was unavailable. A fallback retry also failed, and a later local fallback correctly refused the store lock while the supervisor recovered the shared service. No source edit occurred during that interval. After supervised code-index job `bd18ee2683794015afb5e2c30ce092ac` completed, the exact query succeeded against port 8766 with current `src/cadrumo` results and implementation proceeded.

No production source, neighboring test, compatibility route, test double, destructive worktree command, or unrelated peer change was used. S10 and P02 were not started.
