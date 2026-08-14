---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:853b368b20b57145e79288fdf6d9d2ad72463294b617990b8421e65f1ea963e9'
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

The shared-worktree dependency boundary resolved naturally: the complete canonical extraction and S23 replay code landed together in reachable commit `5a6fcd09e4`. Fresh independent re-review of that enlarged exact set returned PASS with no findings, proving exact extractions, deletion of old inline duplicates, complete constructor migration, and unique durable replay authority.

## Notes

Both semantic RAG corpora remained offline with HTTP 500 responses. The user explicitly waived mandatory RAG and authorized execution from the self-contained plan and linked corpus; no service/process/store mutation or fallback semantic authority was used.

Final verification on the enlarged tree: 214 application-and-persistence operation tests passed in 11.89s; Ruff passed; 37 files were already formatted; BasedPyright reported 0 errors, 0 warnings, and 0 notes; diff hygiene passed. The fresh independent reviewer additionally passed 181 scoped tests under --noconftest.

`uvx vaultspec-core vault check all` exited 0 with 1,318 unrelated shared-corpus warnings; S23 structure, links, placeholders, modified stamps, plan transition, and review evidence are clean.
