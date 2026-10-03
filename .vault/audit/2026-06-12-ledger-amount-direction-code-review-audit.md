---
tags:
  - '#audit'
  - '#ledger-amount-direction'
date: '2026-06-12'
modified: '2026-10-03'
body_hash: 'sha256:a2c9eca2e9029dc91352cc24285b5de9344088f7790db619a6256785514dc79e'
related:
  - '[[2026-06-10-ledger-amount-direction-adr]]'
  - '[[2026-06-10-ledger-amount-direction-research]]'
---

# `ledger-amount-direction` Code Review

## LADR-001 | INFO | No downstream amount-sign direction inference found

Reviewed the implementation against the amount/direction ADR and plan. Ledger ingestion converts source-signed provider values once at the adapter boundary, stores `RawTransaction.amount` as an absolute magnitude, and carries flow through `Transaction.direction` / `ParsedLedgerRow.direction`. Mutation, split/merge, evidence, CLI update/add, filing snapshot, and Renta aggregation consumers no longer infer flow from stored amount signs.

Remaining source-sign references are limited to import provider boundary names/docs/tests such as `direction_from_signed_amount`, plus unrelated non-ledger tax/export helpers. The provider boundary still rejects zero source-signed movements and emits absolute stored amounts.

## LADR-002 | INFO | Full sequential suite gate remains open

Focused gates passed for ledger domain/application/provider/CLI, locale scaffolding/audit, ruff, and Renta aggregation consumers. The first required sequential full-tree command `uv run --no-sync pytest src/aeat -x -q` failed after 4700 passing tests at the retired test; the test passed when rerun in isolation and as part of its module.

A second full-tree attempt failed earlier at the retired test. That failure reproduces in isolation because sibling modelo changes make `ModeloRecord(aeat_accepted=True)` require `external_evidence`, while the migrated-repository fixture still creates accepted filing records without that evidence. This is outside the ledger amount/direction surface and appears in sibling dirty modelo files, so plan step `P05.S15` remains unchecked and this child plan is not formally closable yet.
