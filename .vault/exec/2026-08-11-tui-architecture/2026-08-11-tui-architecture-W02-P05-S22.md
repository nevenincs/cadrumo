---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:87605603ba1051886c753872aa0e2505d78377e72565498ed9e828ed898a19bb'
step_id: 'S22'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# W02.P05.S22 - Implement the durable operation supervisor vertical slice

## Scope

Implement submit, start, inspect, observe, await, respond, reject, request-cancel, detach, settle, and reconcile operations with durable idempotency, exact interaction and lease correlation, definition-bound mutation checks, secure references, and journal compare-and-swap invariants.

## Description

- Grounded the supervisor, interaction, idempotency, cleanup-family, secure-reference, and conflict-scope concepts through fresh code semantic search, whole-file epicentre reads, targeted symbol confirmation, and direct reads of the binding ADR, plan, and S22 audit.
- Implemented canonical operation contracts with credential-free schema-v2 checkpoints, safe interaction events, deterministic conflict-scope references, and strict secure-reference custody.
- Implemented encrypted content-addressed secure-reference storage over the registered secure-object authority and scope-keyed schema-v2 durable leases.
- Bound executor mutations to the registered definition, refusing undeclared phase, effect, interaction, and cleanup-family mutations before mutation.
- Persisted start events, pending and consumed interaction checkpoints, exact single-use response evidence, and idempotency replay evidence through canonical journal compare-and-swap operations.
- Closed the five original S22 review findings: complete-journal idempotency resolution and creation; exact lease-token ownership, expired-owner takeover, and terminal release; valid event-free cancellation transitions; full consumed-checkpoint CAS; and definition-bound terminal effects.
- Closed the renewal and await re-review findings: every supervisor-owned mutation uses the held exact lease and renews it only through a caller-clocked pre-expiry compare-and-swap; a refused renewal retains the durable lease and journal bytes; and `await_terminal` reloads until a terminal snapshot is durable.
- Replaced the create-refusal proof with a real encrypted-SQL and filesystem path scenario that enters `OperationJournal.create` after lease acquisition, refuses there, releases the exact lease, and successfully retries after the conflicting path is removed.

## Outcome

S22 remains open and uncommitted, ready for independent re-review. No plan checkbox, audit record, branch, alternate index, or worktree was changed.

The reachable production history contains the prior remediation:

- `3c9f0a2934` relaxes durable history revision and tail validation for event-free snapshots and makes consumed-interaction prefix comparison bind complete evidence rather than IDs alone.
- `64941ea040` makes idempotent initial creation use `OperationJournal.create`, while normal `commit` refuses an idempotent first snapshot.
- `1eaec01102` captures one supervisor lease token, verifies exact ownership, takes over only an expired predecessor through CAS, validates terminal effects before cleanup, and releases the exact terminal lease.
- `08ef927de9` adds direct supervisor proofs for conflict retry, token mismatch, event-free cancellation plus later terminal event, expired-owner reconciliation and release, and forbidden terminal effect; `022fd40aef` adds full consumed-evidence corruption proofs; `374f719f6d` and `c78e0d73c8` retain formatting and corruption-fixture corrections.

The current worktree completes the outstanding supervisor behavior with direct real-adapter evidence:

- A one-minute held lease renews at a caller-supplied instant before expiry, retains its acquisition, owner, and token identity, remains active after the original window, and settles successfully.
- A competing exact owner causes the original supervisor renewal to refuse; the original journal and durable lease bytes remain byte-for-byte unchanged.
- A nonterminal `await_terminal` call remains pending, observes the real terminal settlement, and returns its durable terminal snapshot.
- A pre-existing journal path with no idempotency claim refuses within journal creation after lease acquisition; exact release leaves the scope acquirable by the retry.

Focused and normal direct verification completed:

- `uv run pytest -q -n 0 -m integration src/cadrumo/application/operations/tests/test_supervisor.py::test_submit_journal_create_refusal_releases_the_exact_lease_for_retry src/cadrumo/application/operations/tests/test_supervisor.py::test_supervisor_renews_exact_lease_before_expiry_and_settles_beyond_original_duration src/cadrumo/application/operations/tests/test_supervisor.py::test_exact_lease_renewal_owner_loss_refuses_without_changing_durable_bytes src/cadrumo/application/operations/tests/test_supervisor.py::test_await_terminal_waits_for_a_real_durable_settlement --disable-warnings --maxfail=1` -> 4 passed in 7.70s.
- `uv run pytest -q -n 0 -m integration src/cadrumo/application/operations/tests/test_supervisor.py --disable-warnings --maxfail=1` -> 17 passed in 11.55s.
- `uv run pytest -q -n 0 -m "unit or integration" src/cadrumo/application/operations/tests src/cadrumo/adapters/persistence/operations/tests --disable-warnings --maxfail=1` -> 205 passed in 45.29s.
- `uv run ruff check src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> all checks passed.
- `uv run ruff format --check src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> 32 files already formatted.
- `uv run basedpyright src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> 0 errors, 0 warnings, 0 notes.
- `git diff --check -- src/cadrumo/application/operations/_supervisor.py src/cadrumo/application/operations/tests/test_supervisor.py` -> clean before the final focused gates.

The prior shared-tree `BucketManifest.status` setup failure did not recur: the normal supervisor and full S22 lanes completed through real secure storage. The direct four-test gate uses the production encrypted-SQL secure-object repository under its existing ephemeral master-key session; it does not use a fake, mock, patch, or substituted persistence adapter.

## Notes

Live code RAG identified `_supervisor.py`, `_journal.py`, `_leases.py`, `_models.py`, `_interactions.py`, `_capabilities.py`, persistence journal and lease adapters, and their direct tests as the canonical implementation cluster. The attempted live vault semantic query was unavailable while the vault index reported a changing state; the updated audit, authorizing ADR, plan, execution record, targeted vault status, and exact-source confirmation supplied the governing evidence.

All remediation tests use actual filesystem repositories and real encrypted SQL secure-object storage. No fakes, mocks, monkeypatches, skips, import shims, global test-configuration changes, plan completion, audit rewrites, Git-history rewrites, alternate indexes, branches, or worktrees were used.

## Final heartbeat and durable-wait closure

- `start` now owns and joins the executor task while it schedules lease renewal at one-third of the configured lease duration, capped at 30 seconds. Scheduler wakeups are not authority: each renewal uses the supervisor caller clock and an exact held-predecessor compare-and-swap; the held owner, token, acquisition instant, and conflict scope remain unchanged.
- Renewal and supervisor transitions are serialized per operation so a heartbeat cannot race executor-published state and falsely lose an exact predecessor. On failed renewal, the supervisor cancels and awaits the executor task before refusing; it leaves the winner lease and original journal bytes unchanged.
- `await_terminal` now treats the durable journal as authoritative, wakes promptly for this supervisor's successful commits, and otherwise uses cancellation-safe exponential backoff from 25ms to 250ms so detached, restarted, and other-process writers remain observable without busy polling.
- New direct production-adapter proofs use real asyncio events, filesystem journal and lease repositories, and encrypted SQL operands: a quiet executor started at `t0` renews beyond its initial lease and settles after that first window; exact owner loss stops and joins the executor while preserving winner bytes; a sustained nonterminal await performs only one to three real journal opens over 130ms before cancellation.

## Final outcome

S22 remains open and uncommitted, ready for independent re-review. No plan checkbox, audit record, branch, alternate index, or worktree was changed.

## Settlement ownership closure

- `settle` now holds the per-operation supervisor lock across exact live-lease proof, declared asynchronous-resource close and removal, terminal journal commit, and exact lease release. A stale supervisor therefore refuses before it can close or remove a resource.
- A direct real-adapter regression starts a declared-resource operation, explicitly releases its lease, lets a replacement acquire the identical definition-subject scope, and proves stale settlement leaves the original resource at zero close calls and preserves both original journal and winner-lease bytes. The valid replacement then starts and settles its own declared resource, which closes exactly once.
- Verification after this closure: focused S22 lifecycle gate 4 passed; supervisor module 21 passed; operation and persistence lanes 209 passed; Ruff check and format, basedpyright, and the scoped diff check are clean.
## Final review and closeout evidence

Independent formal review verdict: PASS. No CRITICAL, HIGH, or MEDIUM finding remains open. The final remediation proves complete-journal idempotency, exact lease-token and conflict-scope ownership, quiet-executor heartbeat renewal, owner-loss cancellation and byte preservation, bounded cross-instance terminal waiting, immutable interaction consumption, and lease proof before resource cleanup.

Final gates on the reviewed tree:

- `uv run pytest -q -m "unit or integration" src/cadrumo/application/operations/tests src/cadrumo/adapters/persistence/operations/tests --disable-warnings --maxfail=1` -> 209 passed in 9.55s.
- `uv run pytest -q -m integration src/cadrumo/application/operations/tests/test_supervisor.py --disable-warnings --maxfail=1` -> 21 passed in 7.60s.
- `uv run pytest -q -m integration src/cadrumo/application/operations/tests/test_supervisor.py -k "stale_settle or quiet_executor or heartbeat_owner_loss or sustained_wait" --disable-warnings --maxfail=1` -> 4 passed in 5.72s.
- Ruff check passed; Ruff format reported 32 files already formatted; BasedPyright reported 0 errors, 0 warnings, and 0 notes.

`uvx vaultspec-core vault check all` exited 0 with 1,385 shared-corpus warnings. Its current modified-stamp findings include the unrelated unresolved status-enum placeholder edit in `2026-08-14-test-harness-sanity-successor-adr`; that shared document is outside S22 and was not modified by this step.
