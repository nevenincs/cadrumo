---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9b23c1b3013421d5b51e7be0c208699948844fa132c858b4b00d42bd5b11597d'
step_id: 'S24'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement aggregate deadline, cooperative cancellation acknowledgement, irreversible-section protection, and cleanup deadlines

## Scope

- `src/cadrumo/application/operations/_supervisor.py`
- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/_execution_context.py`
- `src/cadrumo/application/operations/_executor.py`
- `src/cadrumo/adapters/persistence/operations/_journal.py`

## Description

- Persist absolute execution and cleanup deadlines plus ordered cancellation-request and cancellation-acknowledgement timestamps on `OperationPersistedSnapshot`, rejecting uncorrelated or temporally impossible records.
- Advance the persisted snapshot to strict schema v3. Every v3 record carries each safety fact explicitly, including a factual `null` when a deadline or cancellation fact does not apply; v1 and v2 operation journals are refused without a migration or read-tolerance path.
- Add the typed asynchronous irreversible-section boundary to the cancellation scope. A request remains recordable during the section, while safe-stop acknowledgement is refused until it exits.
- Add positive supervisor policy durations, persist the aggregate deadline at start, request cooperative cancellation on expiry, retain cleanup-deadline escalation as `SETTLING`, and prohibit `CANCELLED` until local executor completion, durable acknowledgement, and owned cleanup completion.
- Prohibit every terminal condition that asserts known completion, including `TIMED_OUT`, until local executor work has stopped and owned cleanup settles. Preserve `INTERRUPTED` as the ADR-defined unknown-ownership and unknown-effect outcome.

## Outcome

Independent review initially found two HIGH defects: `TIMED_OUT` could become durable while executor work remained live, and the new safety facts silently widened schema v2. Both are remediated.

- A real encrypted-operand, filesystem-journal, and owner-lease regression refuses `TIMED_OUT` and `INTERRUPTED` while a known local executor remains live, preserves the nonterminal durable snapshot, then permits the terminal receipt only after completion.
- A fresh recovery supervisor with no local task still settles `INTERRUPTED` after genuine owner loss, retaining the required unknown-effect boundary.
- Raw v1 and v2 filesystem journal records with absent safety fields are rejected unchanged. Fully populated v3 records round-trip through the strict model and real adapter boundary.
- Cancellation requests remain recordable in an irreversible section, acknowledgement is refused until it exits, and cleanup-deadline expiry escalates to `SETTLING` without publishing a false terminal state.

## Notes

The semantic RAG service was offline and the user explicitly waived it. Grounding therefore used the requested accepted decision, research, plan, live source, constructor, persistence, and targeted test inspection; no fallback semantic authority was created.

The live S24 row names only `_supervisor.py`, but its required durable state, executor-facing safety boundary, strict filesystem reader, and directly affected constructors need narrowly coupled edits. No plan prose was altered.

## Final independent closeout

PASS. An independent S24 closeout reran the complete owned boundary after the two remediation findings:

- `uv run pytest -q src/cadrumo/application/operations/tests/test_executor.py src/cadrumo/application/operations/tests/test_journal.py` - `16 passed`.
- `uv run pytest -q -m integration src/cadrumo/application/operations/tests/test_supervisor.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_persistence_integration.py` - `32 passed`.
- Scoped Ruff check passed; all 11 reviewed files passed `ruff format --check`; BasedPyright reported `0 errors, 0 warnings, 0 notes`; and scoped `git diff --check` passed.

Final `uvx vaultspec-core vault check all` exited `0`: the S24 records and plan are clean, with `1,318` shared-corpus warnings outside this closeout. The S24 closeout does not begin or assert completion of S25.
