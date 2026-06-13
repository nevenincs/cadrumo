---
tags:
  - '#plan'
  - '#t6-aggregation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-t6-aggregation-adr]]"
  - "[[2026-04-30-t6-aggregation-research]]"
---

# `t6-aggregation` `implementation` plan

Implement the accepted T6 contract for Modelo 130 aggregation from classified transactions into formula-engine inputs and a Kent-readable casilla ledger.

## Proposed Changes

Add a new financial aggregation package, wire it into `aeat financial aggregate`, register JSON and error contracts, replace workflow's default JSON-file inputs provider with the financial provider when a catalogue is available, and update the coverage matrices to describe shipped T6 behavior.

## Tasks

- `Models and period`
  1. Add strict frozen `Period`, `CasillaProvenance`, and `CasillaAggregation`.
  1. Add typed aggregation errors and registry rows.
  1. Verify model validation, immutability, and serialization.
- `Aggregation backend`
  1. Implement in-memory aggregation over `TransactionCatalogue`.
  1. Apply period filtering, classification checks, category mappings, and proportionality factors.
  1. Verify real catalogue fixtures produce Modelo 130 `01` / `02` values and provenance.
- `Inputs provider`
  1. Implement `FinancialFilingInputsProvider` against `TransactionCatalogueRepository`.
  1. Wire workflow default engine to prefer the financial provider.
  1. Verify `Engine.derive()` consumes the returned Decimal mapping.
- `CLI and JSON`
  1. Add `aeat financial aggregate --modelo --period [--json]`.
  1. Register `financial aggregate` in `aeat.entrypoints.cli._schemas`.
  1. Render human output through trilingual messages and `AEAT_OUTPUT_LANGUAGE`.
- `Coverage docs`
  1. Update the T6 row in `docs/coverage/pipeline.md`.
  1. Update the Kent capability row in `docs/coverage/kent-capabilities.md`.
  1. Update Modelo 130 in `docs/coverage/modelos.md`, leaving M303 aggregation deferred.
- `Verification and review`
  1. Run focused financial aggregation, CLI, workflow, and formula tests.
  1. Run `just test-cov` if feasible in this environment.
  1. Run vaultspec code review and address findings.
  1. Commit with a conventional commit, push, and open the PR.

## Parallelization

The backend and CLI are tightly coupled and should be implemented serially. The coverage documentation review can run as a separate documentation subagent workflow after code behavior is known. The final code review should run after all implementation and docs are complete.

## Verification

Mission success is a real catalogue fixture where classified Q1 transactions aggregate to Modelo 130 input casillas, `Engine.derive()` computes the expected payment, the CLI emits both human and JSON ledgers, and `workflow next` can build from the provider instead of a hand-authored JSON inputs file. Tests must not use mocks, monkeypatches, skips, or tautological assertions.
