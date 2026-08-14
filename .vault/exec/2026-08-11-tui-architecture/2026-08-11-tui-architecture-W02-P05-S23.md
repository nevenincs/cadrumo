---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7be09a5526e8398bbffd3a016e5ae9b5cc59ff2dad3e1ffbb0c42e90ddd43e4f'
step_id: 'S23'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# W02.P05.S23 - Implement bounded cursor replay through the supervisor

## Scope

Implement cursor replay and bounded live observation without making subscriber connectivity operation authority.

## Description

- Re-read the binding plan, governing TUI architecture ADR and research, S22 evidence, and complete supervisor, replay-contract, event-stream, and persistence-journal epicenters under the user's explicit offline-RAG waiver.
- Confirm with targeted repository search that `OperationReplayPage` owns replay result semantics and `OperationJournalRepository.read_after` is the sole durable replay implementation.
- Inject the canonical `OperationEventStream` into `OperationSupervisor` and expose a thin bounded `replay` delegation without a second cursor, history, validation, subscriber, or connectivity authority.
- Add real encrypted-SQL and filesystem tests covering `PAGE`, `CAUGHT_UP`, `UNKNOWN_OPERATION`, bounded two-plus-one pagination, monotonic cursor advancement, repeated-page idempotence, and a fresh observer over retained journal state.

## Outcome

Implementation and independent Sol Medium review are complete. Review verdict: PASS with no CRITICAL, HIGH, or MEDIUM findings. Focused verification passed 26 implementation tests; the independent review reran 12 focused tests, Ruff, BasedPyright, and diff hygiene successfully.

The row remains open and uncommitted pending a shared-worktree dependency-delivery boundary. The current reviewed supervisor and journal diffs preserve pre-existing extractions into `_execution_context.py`, `_supervisor_lease.py`, and `_journal_validation.py`. Those untracked modules are required imports after their former inline definitions were removed. Omitting them from a path-scoped S23 commit would break runtime imports, while absorbing them without ownership would capture peer WIP. S23 will close only after their owner lands them or explicitly coordinates atomic inclusion.

## Notes

Both semantic RAG corpora remained offline with HTTP 500 responses. The user explicitly waived mandatory RAG and authorized execution from the self-contained plan and linked corpus; no service/process/store mutation or fallback semantic authority was used.
