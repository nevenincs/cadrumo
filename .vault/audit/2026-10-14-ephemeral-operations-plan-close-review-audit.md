---
tags:
  - '#audit'
  - '#ephemeral-operations'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:22c22694e826302d07e54f359b9f356ed2f265e29137a7a1aa42e9de9d01a6db'
related:
  - "[[2026-10-14-ephemeral-operations-plan]]"
---

# `ephemeral-operations` audit: `plan close review`

## Scope

Plan-close review of Steps S01-S05 of the ephemeral-operations plan, covering the change set from base `f40cd28279` to target `d2c52ff625`.

Verdict: PASS. No critical or high finding. Four medium and two low findings are recorded below.

## Findings

### provenance-durable-write | medium | An ephemeral read still writes an orphaned encrypted provenance row on every page

`_supervisor_submission.py:147-152` writes admission provenance through `self._operands` before `_register_durability`. `DurabilityRoutedOperationPersistence.put` (`durability_router.py:211-212`) always goes to the durable store. `operation_host.py:431` captures provenance for every frontend submission, so each ephemeral page writes one unreferenced encrypted row. The error detail written by `_settle_executor_failure` does the same. Fix: register durability before writing, and route both writes through `_operands_for(operation_id)`. Add a row-count test.

### shared-operand-eviction | medium | Evicting one ephemeral operation removes operands a newer one still uses

`ephemeral_store.py:156-160` drops the evicted owner's digests, while `put_for` (`ephemeral_store.py:329-337`) stores operands content-addressed and shared. An identical newer read loses its result: the caller sees "secure reference absent" instead of `unknown_operation`. Fix: keep per-owner reference counts, or key operands by operation.

### unsettled-ephemeral-tracking | medium | The worker host tracks ephemeral reads as unsettled; an evicted one leaks and re-takes the journal lock

`operation_host.py:435` adds ephemeral reads to `_unsettled`. `_settle_lapsed_operations` (`operation_host.py:374-383`) then loads each id through the router. After eviction, `routes_ephemeral` is false (`durability_router.py:82-97`), so the durable load takes the journal lock and raises `RepositoryError`, and the id is retried every 30 s indefinitely. Fix: never track ephemeral operations, or drop them at settlement. Add the sweep to the lock-count proof.

### decrypted-result-retention | medium | Settled profile pages stay decrypted in worker memory with no time bound

`EPHEMERAL_SETTLED_RETENTION = 256` (`ephemeral_store.py:60`) keeps plaintext results for the worker's lifetime. The persistence rule asks that decrypted material have a bounded lifetime. Fix: add an age bound, or release a result after it is read. Confirm whether profile lock or sign-out ends the worker.

### lock-proof-positive-control | low | The runtime journal assertion has no positive control

The `test_frontend_client.py` check passes vacuously when the journal directory is absent. Assert that a recorded operation from the same run is present.

### mid-read-loss-evidence | low | Mid-read worker loss is shown only by a fresh router after settlement

No test kills a worker mid-read and observes `unknown_operation` through the runtime.

## Recommendations

- `provenance-durable-write`: register durability before the provenance write, route through `_operands_for(operation_id)`, and add a row-count test.
- `shared-operand-eviction`: add per-owner reference counts or key operands by operation, and test an identical newer read after eviction.
- `unsettled-ephemeral-tracking`: stop tracking ephemeral operations in `_unsettled`, or drop them at settlement, and extend the lock-count proof to the lapsed-operation sweep.
- `decrypted-result-retention`: bound settled-result age or release on read, and establish what ends the worker.
- `lock-proof-positive-control`: assert a recorded operation exists in the journal from the same run.
- `mid-read-loss-evidence`: add a runtime test that kills a worker mid-read.
