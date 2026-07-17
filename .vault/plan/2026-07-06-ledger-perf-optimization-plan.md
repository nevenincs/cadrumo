---
tags:
  - '#plan'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-07-05-ledger-latency-budget-adr]]'
  - '[[2026-07-06-ledger-perf-optimization-reference]]'
  - '[[2026-07-06-ledger-perf-optimization-research]]'
---

# `ledger-latency-budget` plan

## Description

This plan executes the grounded optimization follow-up to the accepted
`ledger-latency-budget` decision. The current branch has already landed the O2
period-first partition, per-window calculate memoization, per-transaction encrypted
rows, and decryption-free save reconciliation, so the plan does not re-implement those
surfaces. It focuses on the residual costs still present at HEAD: targeted partition
reads are N+1, out-of-window diagnostics allocate per excluded row, `Transaction`
validation still runs through a Python-mode before-validator, and single-row mutations
still serialize/hash the whole incoming catalogue.

The plan is intentionally staged. Wave W02 is the highest-confidence read-path quick
win and does not change tax semantics or diagnostic taxonomy. Wave W03 is diagnostics
only but changes the operator-visible issue shape, so it first amends the accepted ADR.
Wave W04 changes validation mechanics and is gated by strict JSON roundtrips plus
tamper tests. Wave W05 measures the write path and creates a separate dirty-set decision
surface only if the residual is material.

## Wave `W01` - baseline and stale finding reconciliation

This Wave pins the current branch against the Fable review, separates already-landed O2 and write-amplification work from remaining residual costs, and gives later Waves a measured baseline before changing storage or diagnostic contracts.

### Phase `W01.P01` - ground current surfaces

This Phase records the RAG-grounded implementation surfaces and stale-finding deltas so execution starts from HEAD, not from the older review snapshot.

- [x] `W01.P01.S01` - Record current O2 partition, single JSON decode, and write-path drift findings; `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md`.
- [x] `W01.P01.S02` - Persist Fable synthesis, accepted constraints, and open residual tiers; `.vault/research/2026-07-06-ledger-perf-optimization-research.md`.
- [x] `W01.P01.S03` - Refresh the scale benchmark to report partition load count and paired P95 deltas; `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`.

### Phase `W01.P02` - protect landed contracts

This Phase locks the already-landed O2 and per-row storage behavior so later optimizations do not reopen the silent-drop or full-rewrite classes.

- [x] `W01.P02.S04` - Pin date-index completeness fallback and partition parity around current O2 behavior; `src/aeat/adapters/persistence/profile/tests/test_transactions_repository.py`.
- [x] `W01.P02.S05` - Pin per-transaction save reconciliation so unchanged rows are not encrypted or upserted; `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`.
- [x] `W01.P02.S06` - Pin transaction timestamp witness drift detection without a second full JSON decode; `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`.

## Wave `W02` - batch partition reads

This Wave collapses the remaining partition-read N+1 by adding a secure-object batch load primitive and routing the transaction repository partition through one SQL read per window. It depends on Wave W01's parity pins and feeds the diagnostic and validator Waves with a lower M130 baseline.

### Phase `W02.P03` - secure-object batch primitive

This Phase adds one storage-layer targeted batch read that preserves the existing classification, schema-version, AEAD, and revision-lineage checks for every returned row.

- [x] `W02.P03.S07` - Add any batch-read result contract needed by targeted secure-object loads; `src/aeat/adapters/persistence/storage/sql/_secure_object_records.py`.
- [x] `W02.P03.S08` - Implement a namespace and object-key batch load over one SQL IN query; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W02.P03.S09` - Prove batch load returns the same decrypted rows and failures as repeated single loads; `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py`.

### Phase `W02.P04` - transaction partition adoption

This Phase consumes the storage batch primitive in the transaction catalogue without altering the date-index completeness gate or stale-index full-scan fallback.

- [x] `W02.P04.S10` - Replace load-for-date-range per-id secure-object reads with the batch primitive; `src/aeat/adapters/persistence/profile/transactions.py`.
- [x] `W02.P04.S11` - Replace partition-by-date-range per-id secure-object reads with the batch primitive; `src/aeat/adapters/persistence/profile/transactions.py`.
- [x] `W02.P04.S12` - Prove targeted partition reads use one storage batch while preserving in-window and out-of-window sets; `src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`.

### Phase `W02.P05` - M130 read benchmark

This Phase reruns the scale budget after the batch-read change and records whether the quick win is enough before diagnostic and validation work land.

- [x] `W02.P05.S13` - Run the M130 scale benchmark and record read, calculate, and annual residuals; `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`.
- [x] `W02.P05.S14` - Update the code reference with paired before and after batch-read measurements; `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md`.

## Wave `W03` - out-of-window diagnostic summary

This Wave replaces per-row out-of-window diagnostic allocation with one summary diagnostic per resolver after the accepted ADR explicitly covers the summary contract. It depends on Wave W02 because batch-read measurements decide how much residual GC relief is still needed.

### Phase `W03.P06` - summary contract decision

This Phase records the diagnostics-channel contract change before implementation, keeping declared tax values and the plaintext date-index schema unchanged.

- [x] `W03.P06.S15` - Amend the latency ADR to authorize count and date-span OUTSIDE_PERIOD summaries; `.vault/adr/2026-07-05-ledger-latency-budget-adr.md`.
- [x] `W03.P06.S16` - Record the summary contract and consumer impact in the research artifact; `.vault/research/2026-07-06-ledger-perf-optimization-research.md`.

### Phase `W03.P07` - partition summary payload

This Phase moves the out-of-window side of the partition from many pydantic stubs to a compact count plus date-span payload.

- [x] `W03.P07.S17` - Add the compact out-of-window summary model and partition field; `src/aeat/domain/transactions/_models.py and src/aeat/domain/transactions/__init__.py`.
- [x] `W03.P07.S18` - Update the transaction repository protocol to describe summary diagnostics; `src/aeat/domain/transactions/_protocols.py`.
- [x] `W03.P07.S19` - Emit count and date-span summaries from indexed and fallback partitions; `src/aeat/adapters/persistence/profile/transactions.py and src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`.

### Phase `W03.P08` - aggregation and source diagnostics

This Phase threads the compact summary through each affected aggregation resolver and the source-diagnostic channel without constructing one issue per excluded transaction.

- [x] `W03.P08.S20` - Add source diagnostic fields or message helpers for summarized OUTSIDE_PERIOD counts; `src/aeat/application/aggregation/_source_mesh.py and src/aeat/application/aggregation/tests/test_source_mesh.py`.
- [x] `W03.P08.S21` - Convert IVA repository-backed aggregation to emit the out-of-window summary; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W03.P08.S22` - Convert M130 income aggregation to emit the out-of-window summary; `src/aeat/application/aggregation/_renta_income_ledger.py`.
- [x] `W03.P08.S23` - Convert M130 gasto aggregation to emit the out-of-window summary; `src/aeat/application/aggregation/_renta_gasto_ledger.py`.
- [x] `W03.P08.S24` - Convert impatriado income aggregation to emit the out-of-window summary; `src/aeat/application/aggregation/_impatriado_income_ledger.py`.
- [x] `W03.P08.S25` - Map summarized aggregation outcomes into one source diagnostic per resolver; `src/aeat/application/aggregation/_modelo_bindings.py`.

### Phase `W03.P09` - summary regression tests

This Phase replaces per-row diagnostic assertions with count and date-span assertions while preserving observation, casilla, and provenance parity.

- [x] `W03.P09.S26` - Update IVA out-of-window tests for one summary diagnostic; `src/aeat/application/aggregation/tests/test_iva_ledger.py`.
- [x] `W03.P09.S27` - Update M130 and annual M100 income out-of-window tests for one summary diagnostic; `src/aeat/application/aggregation/tests/test_renta_income_aggregation.py and src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py`.
- [x] `W03.P09.S28` - Update M130 gasto out-of-window tests for one summary diagnostic; `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py`.
- [x] `W03.P09.S29` - Update impatriado out-of-window tests for one summary diagnostic; `src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py`.
- [x] `W03.P09.S30` - Update source-mesh ledger tests for summarized diagnostics; `src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py`.

## Wave `W04` - transaction validation fast path

This Wave removes the remaining Python-mode validation waste from Transaction loading after the read-path and diagnostic allocation costs are lower. It keeps the derived transaction id invariant and timestamp drift checks intact.

### Phase `W04.P10` - derived id validator restructure

This Phase moves transaction id enforcement to the post-parse model boundary so pydantic-core handles native enum, decimal, date, and datetime coercion.

- [x] `W04.P10.S31` - Replace the before-validator id derivation path with an after-validator invariant; `src/aeat/domain/transactions/_models.py`.
- [x] `W04.P10.S32` - Remove obsolete manual transaction coercion helpers after callers are reconciled; `src/aeat/domain/transactions/_models.py`.
- [x] `W04.P10.S33` - Preserve transaction construction paths that omit explicit transaction ids; `src/aeat/domain/transactions/_service.py`.

### Phase `W04.P11` - validator regression tests

This Phase proves the validator restructure is behavior-preserving across JSON persistence, direct model construction, and tamper rejection.

- [x] `W04.P11.S34` - Add transaction JSON roundtrip coverage for non-default fields and derived ids; `src/aeat/domain/transactions/tests/test_models.py`.
- [x] `W04.P11.S35` - Add tampered transaction id rejection coverage for storage-shaped JSON; `src/aeat/domain/transactions/tests/test_models.py`.
- [x] `W04.P11.S36` - Add encrypted repository roundtrip coverage for validator JSON-mode loading; `src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`.

### Phase `W04.P12` - validation benchmark gate

This Phase measures the read and calculate paths again after validator restructuring and records whether listing and annual residuals still need another lever.

- [x] `W04.P12.S37` - Run the domain transaction model tests after the validator rewrite and fix catalogue JSON-mode loading regressions; `src/aeat/domain/transactions/_models.py and src/aeat/domain/transactions/tests`.
- [x] `W04.P12.S38` - Run the transaction repository tests after the validator rewrite; `src/aeat/adapters/persistence/profile/tests`.
- [x] `W04.P12.S39` - Run the scale benchmark and record validator delta in the reference; `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`.

## Wave `W05` - write-path and residual triage

This Wave measures residual costs outside the read-path budget, especially single-row ledger mutations, and separates follow-up ADR work from the already-authorized M130 read optimization. It runs after Waves W02 through W04 so residual attribution is clean.

### Phase `W05.P13` - single-row mutation measurement

This Phase quantifies the remaining O(n) serialize and hash work in transaction catalogue saves without changing the mutation contract yet.

- [x] `W05.P13.S40` - Add a 30k-row single-transaction mutation benchmark to expose save-side residuals; `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`.
- [x] `W05.P13.S41` - Record whether namespace hash scans or transaction serialization dominate mutation latency; `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md`.

### Phase `W05.P14` - dirty-set decision handoff

This Phase creates a separate decision surface if the mutation benchmark shows a material residual, because dirty-set writes alter repository mutation semantics beyond the accepted read-path ADR.

- [x] `W05.P14.S42` - Draft the dirty-set mutation contract research if write latency remains material; `.vault/research/2026-07-06-ledger-perf-optimization-research.md`.
- [x] `W05.P14.S43` - Draft a follow-up ADR for dirty-set save semantics before implementation; `.vault/adr/2026-07-06-ledger-latency-budget-adr.md`.

### Phase `W05.P15` - residual cache confirmation

This Phase verifies that previously completed registry caching and the new secure-object batch path are not still visible residuals before closing the campaign.

- [x] `W05.P15.S44` - Confirm registry authority cache behavior stays covered by the existing authority tests; `src/aeat/domain/calculations/registry/tests/test_authority.py`.
- [x] `W05.P15.S45` - Confirm secure-object batch read removes repeated session setup from partition reads; `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py`.
- [x] `W05.P15.S46` - Run the feature-surface gate over the touched storage, transaction, aggregation, and modelo paths; `src/aeat`.

## Parallelization

Wave W01 must run first so every later execution record cites current-state facts, not
the older review snapshot. Within W01, P01 and P02 can run in parallel after the first
reference update, because they touch documentation and tests.

Wave W02 should land before W03 and W04. The secure-object batch primitive in P03 blocks
transaction adoption in P04, and P05 must run after P04. W03 depends on W02's benchmark
result so the team can decide whether the summary contract is still needed. Inside W03,
P06 blocks P07 through P09 because summary diagnostics need an explicit ADR amendment.
The four aggregator conversion steps in P08 can run in parallel after P07.

Wave W04 can run after W02 and either before or after W03 if the summary contract is
still under review, but its benchmark verdict should be recorded after any W03 work that
lands. Wave W05 runs last; it is residual attribution and decision handoff, not part of
the authorized read-path optimization slice.

## Verification

The plan is successful when the paired scale benchmark shows M130 calculate under the
3.0s P95 budget or the remaining over-budget residual is isolated in W05 with a new ADR
or explicit deferral. Each implementation Wave must preserve observation, casilla value,
and source-provenance parity for in-window rows.

Required gates are focused and real-behavior only: secure-object SQL tests for the batch
primitive, transaction repository date-index and roundtrip tests, the four aggregation
test modules touched by out-of-window diagnostics, transaction domain model tests,
transaction repository tests, and the scale benchmark. No fake repositories,
monkeypatches, skips, xfails, or tautological expected values are acceptable.

No Step may be checked complete without a matching exec record or a deferred carry-forward
note in a close audit. Before close, run `vaultspec-core vault plan check` for this plan
and the feature-surface gate over the touched storage, transaction, aggregation, and
modelo paths.
