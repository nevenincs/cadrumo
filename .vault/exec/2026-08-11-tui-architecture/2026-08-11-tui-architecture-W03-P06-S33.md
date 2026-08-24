---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:56c1a420d733274b9196e93bfc550c57db853ca7abe5dd4b19094653bbfa5b58'
step_id: 'S33'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Prove the complete censal operation lifecycle and effect boundaries

## Scope

- `src/cadrumo/application/user_profile/tests/test_censal_operation.py`

## Description

- Compose the production censo executor, supervisor, filesystem journal and leases, encrypted secure references, encrypted profile repository, a real loopback HTTP acquisition over the captured AEAT fixture and canonical parser, and typed boundary seams into one canonical lifecycle matrix.
- Prove waiting-for-review publishes no profile or event-history write.
- Prove each individual adopt choice and apply-all produce exactly the reviewed facts, leave preserved paths absent, and emit exact divergence axes, artefact values, and sources.
- Prove detach, expired-lease takeover, and resume retain one acquisition and consume the durable secure operand.
- Prove reject and stale exact-baseline refusal never apply reviewed effects.
- Prove cancellation before irreversible entry acknowledges NONE, writes nothing, settles, completes cleanup, and releases the durable lease.
- Prove successful settlement likewise completes cleanup and releases the durable lease.

## Outcome

- Seven real lifecycle cases cover the required effect, recovery, cancellation, and cleanup matrix without mocks, patches, skips, or a second writer.
- Acquisition now returns the application-owned `CensalOperationAcquisition` contract. The executor registers its idempotently closeable resource with supervisor cleanup, then closes it at the completed-read boundary before publishing a detachable review; supervisor ownership remains the cleanup retry path.
- A dedicated restart case proves the original owner closes the loopback acquisition before detach, the expired-lease replacement refreshes the pending revision, applies the stored secure operand with zero additional HTTP acquisition, and releases its exact lease after settlement.
- Apply cases prove one and only one `CENSO_APPLIED` history delta with the exact adopted and divergence counts.
- Focused S33 result: `7 passed`; the full feasible censo lane reports `23 passed`; Ruff passes; BasedPyright reports `0 errors, 0 warnings, 0 notes`; `git diff --check` reports only pre-existing CRLF normalization warnings in unrelated shared-worktree files.

## Notes

- Lower-level S29-S31 infrastructure helpers are reused rather than restated; S33 owns only the composed acceptance matrix.
- Live async resources remain process-local and are never claimed by the replacement supervisor. Their authoritative lifecycle ends when the remote read has been converted into the durable reviewed operand, before detachment; the replacement owns only its newly created continuation resources.
- The shared plan checkbox remains untouched for the coordinating session.
