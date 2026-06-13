---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Ledger Amount Direction Closeout Status

## Completed Plan Items

Completed `P01.S01` through `P04.S14` and `P05.S16`. The plan now stands at 15 of 16 steps complete. `P05.S15` remains open because the required full sequential suite did not complete before timeout.

## Files Touched

Implementation and tests touched: `src/aeat/application/aggregation/_ledger_filing_snapshot.py`, `src/aeat/application/aggregation/_renta_ledger.py`, `src/aeat/application/aggregation/tests/test_renta_ledger_helpers.py`, `src/aeat/application/ledger/_actions_import.py`, `src/aeat/application/ledger/_evidence_split.py`, `src/aeat/application/ledger/tests/test_evidence_split.py`, `src/aeat/application/ledger/tests/test_merge.py`, `src/aeat/domain/transactions/_models.py`, `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/tests/test_ledger_validation_paths.py`, and `src/aeat/entrypoints/cli/tests/test_ledger_corpus_journeys.py`.

Locale and evidence files touched: `src/aeat/locales/ca.yml`, `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, `src/aeat/locales/hu.yml`, `src/aeat/application/ledger/_actions_import.py`, `.vault/plan/2026-06-10-ledger-amount-direction-plan.md`, `.vault/exec/2026-06-10-ledger-amount-direction/*.md`, and `.vault/audit/2026-06-12-ledger-amount-direction-code-review-audit.md`.

## Tests And Checks

Passed: `uv run --no-sync python -m aeat.locales scaffold --check`; `uv run --no-sync python -m aeat.locales audit`; focused ledger/provider/domain/CLI pytest gates; `uv run --no-sync pytest src/aeat/application/aggregation/tests/test_renta_ledger_helpers.py src/aeat/application/aggregation/tests/test_renta_ledger.py src/aeat/application/aggregation/tests/test_renta_ledger_aggregation.py -q`; targeted `ruff check` commands over touched code.

Incomplete: `uv run --no-sync pytest src/aeat -x -q` failed on two later attempts. The first failure was `src/aeat/application/modelo/tests/test_verificado_completo_regression.py::test_verify_grants_when_required_casillas_supplied_m130` after 4700 passing tests; that test passed when rerun alone and in its module. The second failure was `src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories_part1.py::test_modelo_catalogue_defaults_isolate_bucket_writes` after 2577 passing tests; that failure reproduces in isolation because sibling modelo dirty state now requires `external_evidence` for accepted filing records while the migrated-repository fixture still omits it.

## Remaining Sign Callers

No downstream stored-ledger consumer was found inferring direction from stored amount signs. Remaining sign-derived direction handling is the allowed import-provider boundary, where source-signed bank/export values are converted once into absolute `RawTransaction.amount` plus authoritative `direction`.

## Closure

This child plan should not be marked closed until `P05.S15` has a completed full sequential suite result. The current blocker is outside the ledger amount/direction surface and should be resolved by the sibling modelo/persistence work owner or on a clean shared tree.
