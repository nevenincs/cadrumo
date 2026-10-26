---
tags:
  - '#plan'
  - '#ephemeral-operations'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-08-11-tui-architecture-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:9e6ccda0694e7fd510794315c9edbaa275832f51d08926f2d25d5ec9ba61dbec'
---

# `ephemeral-operations` plan

Run no-effect reads without durable journaling, as the accepted operation-envelope decision already permits.

## Description

Approved 2026-10-14. Basis: operator directive 2026-10-14 to address every failing test, relayed by the orchestrator; the plan implements accepted `2026-08-11-tui-architecture-adr` D5.

Each page of a profile view is its own durable read operation. Every page takes the profile's one journal root lock about 25 times, writes a journal file and keeps it. Under host load the 60 s whole-view budget (`src/cadrumo/adapters/local_runtime/frontend_profile_view_client.py:183`) expired across four pages, with one journal lock held 7.4 s. The docs-sequence profile-view test under `-n 2` and the packaged TUI overview read both failed this way. Widening the budget is excluded by the startup-performance audit's widened-deadlines finding.

D5 lets an operation declare `EPHEMERAL` durability when lost observation cannot conceal an effect requiring reconciliation. The capability model enforces that declaration (effect `NONE` only, no replay, no conflict scope; `src/cadrumo/application/operations/capabilities.py:98-104`). No operation declares it, though, and the supervisor journals every operation through the same durable ports. This plan routes ephemeral operations to an in-memory store behind those same ports. Supervision, receipts, observation and result release therefore behave as before, and each ephemeral operation exists only for the life of its worker. The terminal receipt stays exact-profile and no-effect, as rule 12 requires. An ephemeral read lost with its process is answered as an unknown operation; D5 accepts that loss for an operation with no effect. Only `user-profile.view` is declared ephemeral here; other reads can follow on the same mechanism.

Decision coverage: `2026-08-11-tui-architecture-adr` D5 governs. No new costly decision is involved.

## Steps

- [x] `S01` - Add an in-memory operation store implementing the journal, event-stream, observation-reader, lease and secure-reference ports (application/operations/persistence/journal.py:387-520) with the durable adapter's create, commit, settlement, replay and observation semantics (adapters/persistence/operations/journal.py:270-384, _journal_validation.validate_advance), keyed per operation so ephemeral leases never contend; `src/cadrumo/adapters/persistence/operations/ephemeral_store.py, its owning tests`.
- [x] `S02` - Route each operation to the in-memory store or the durable journal by its definition's declared durability at create, and by operation id afterwards; keep recovery inventory and idempotency durable-only, and compose the router where the worker builds its supervisor (entrypoints/operation_composition.py:3213-3235, application/operations/composition.py:240); `src/cadrumo/adapters/persistence/operations/durability_router.py, src/cadrumo/entrypoints/operation_composition.py`.
- [x] `S03` - Serve frontend observe and result-page reads of an ephemeral operation through the composed router, which the observation and result services already read (application/operations/composition.py:297-298), and prove that an operation lost with its process answers both as the typed unknown-operation refusal; `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`.
- [x] `S04` - Declare user-profile.view EPHEMERAL with effect NONE only, no replay and no conflict scope (capabilities.py:98-104; user_profile/operations.py:156), and regenerate the operation contract manifest; `src/cadrumo/application/user_profile/operations.py, src/cadrumo/_data/operations/contract_manifest.json`.
- [x] `S05` - Prove it: an ephemeral page read takes zero journal-lock acquisitions and writes no journal file; a durable read is unchanged; a worker ended mid-read leaves no record and no effect and the frontend gets unknown-operation; the docs-sequence profile-view test and the packaged TUI overview read pass under -n 2 with the 60 s view budget unchanged; `src/cadrumo/adapters/persistence/operations/tests, src/cadrumo/entrypoints/runtime/tests, dev/docs/sequences/tests/test_runner.py`.
- [x] `S06` - Fix plan-close review finding provenance-durable-write: register an operation's durability before any operand write and route admission provenance and opted-in error detail through the operation's own operand store, proven by zero operation secure-object rows after an ephemeral read through the runtime; `src/cadrumo/application/operations/_supervisor_submission.py, src/cadrumo/application/operations/_supervisor_execution.py, src/cadrumo/entrypoints/runtime/tests/test_frontend_client.py`.
- [x] `S07` - Fix plan-close review finding shared-operand-eviction: count each content-addressed ephemeral operand's owners so evicting one operation never removes an operand another still references, proven by two identical reads and eviction of the older; `src/cadrumo/adapters/persistence/operations/ephemeral_store.py, src/cadrumo/adapters/persistence/operations/tests/test_ephemeral_store.py`.
- [x] `S08` - Fix plan-close review finding unsettled-ephemeral-tracking: keep ephemeral operations out of the runtime host's lapsed-owner sweep, and add the sweep to the zero journal-lock proof; `src/cadrumo/entrypoints/runtime/operation_host.py, src/cadrumo/entrypoints/runtime/tests`.
- [x] `S09` - Fix plan-close review finding decrypted-result-retention: release a settled ephemeral operation once its result has been read and after an age bound, and clear the store when the worker's last session locks or signs out if the worker outlives it; `src/cadrumo/adapters/persistence/operations/ephemeral_store.py, src/cadrumo/adapters/persistence/operations/durability_router.py, src/cadrumo/adapters/persistence/operations/tests`.
- [x] `S10` - Fix plan-close review lows: give the profile-view journal assertion a positive control from a recorded operation in the same run, and prove a worker ended during an ephemeral read answers unknown_operation through the runtime; `src/cadrumo/entrypoints/runtime/tests/test_frontend_client.py`.

## Parallelization

Sequential. S02 routes to the store S01 adds; S03 serves what S02 routes; S04 declares the first ephemeral operation only once S01-S03 can carry it; S05 proves the whole path.

## Verification

- An ephemeral profile-view page acquires the journal root lock zero times and leaves no journal file, counted through the real adapter.
- A durable operation's journal behaviour is unchanged, shown by the existing operations and supervisor suites.
- A worker ended mid-read leaves no record and no effect, and the frontend receives the typed unknown-operation refusal.
- `dev/docs/sequences/tests/test_runner.py::test_sequence_profile_view_uses_fresh_runtime_proof_and_exact_profile` and the packaged TUI overview read pass under `-n 2`, with the 60 s view budget unchanged.
- `just check-types`, `just check-import-boundaries`, the contract-manifest drift check and ruff pass on the touched files.
