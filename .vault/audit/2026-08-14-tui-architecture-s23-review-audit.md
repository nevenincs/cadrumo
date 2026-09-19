---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:0529ff415221ed73b52e6c4826da85af13ce23ebe1f7f49eb79ee8c9f7cdebb2'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W02.P05.S23 replay and observation review`

## Scope

Independent formal review of `W02.P05.S23` against the open binding plan row,
the replay and projection decisions in the governing ADR and research, the
production `OperationSupervisor`, `OperationEventStream`, `OperationReplayPage`,
and `OperationJournalRepository.read_after` implementations, the complete
constructor census, and the focused supervisor, replay, executor-contract, and
adapter tests. The user explicitly waived RAG because semantic discovery was
offline; this review therefore used the named canonical documents and a direct
source and diff inspection as its grounding basis.

The review also adjudicated the pre-existing untracked supervisor and journal
extractions visible in the shared worktree. `OperationSupervisor` now imports
`DefinitionBoundContext` and `OperationSupervisorLeaseMixin` after their former
inline definitions were removed, while `OperationJournalRepository` imports
`OperationJournalRecord` and `validate_advance` after its inline validation was
removed. Those extraction modules are required reachable dependencies of the
current S23 delivery shape: they must either land atomically with the affected
tracked files under coordinated ownership or be committed by their owner before
S23. Omitting them from a path-scoped S23 commit would leave broken imports and
is not an admissible delivery boundary.

## Findings

PASS. No correctness, authority, safety, or test-quality findings were found.

The supervisor receives `OperationEventStream` explicitly and its replay surface
is a thin delegation to `read_after`; it neither validates replay pages again nor
owns a second cursor, history, subscriber, or connectivity authority. The durable
adapter remains the sole replay implementation and returns bounded, exclusive,
contiguous pages with typed `PAGE`, `CAUGHT_UP`, and `UNKNOWN_OPERATION` results.
The real-adapter supervisor proof exercises all three results, repeated-page
idempotence, bounded pagination, and monotonically advancing cursors through a
fresh observer over the retained journal. Every production and test constructor
site supplies the new event-stream dependency.

Focused verification passed: 12 tests across `test_supervisor_replay.py`,
`test_supervisor.py`, `test_executor_contract.py`, and the adapter journal suite;
Ruff passed for the complete reachable diff surface; BasedPyright reported zero
errors, warnings, or notes; and `git diff --check` passed for the reviewed paths.

## Recommendations

No implementation changes are required. Preserve the dependency-delivery
boundary recorded in Scope, leave `W02.P05.S23` open until its authorized owner
records execution and delivery, and do not treat subscriber lifetime as
operation state in later observation surfaces.
## Enlarged exact-delivery re-review

PASS. A fresh re-review of the enlarged exact delivery found no correctness,
authority, safety, ownership, migration, import-reachability, or test-quality
findings.

The enlarged boundary now includes `_execution_context.py`,
`_supervisor_lease.py`, and `_journal_validation.py` alongside their consumers.
A mechanical AST comparison against `HEAD` confirmed that every extracted class,
method, and validation helper is unchanged except for the intentional canonical
class-name promotion from `_DefinitionBoundContext` to
`DefinitionBoundContext` and `_OperationJournalRecord` to
`OperationJournalRecord`. The former inline definitions are deleted, targeted
repository search found no old-name or substitutable duplicate implementation,
and the complete import graph is reachable. The active collaboration roster had
no extraction owner still working: the lease-contract agent was complete, and
only the campaign executor and this independent reviewer remained active.
Therefore the earlier dependency-delivery caution is resolved for this enlarged
atomic scope; omitting any of the three extraction modules would still be invalid,
but including them captures no active peer work and introduces no shim.

`OperationSupervisor.replay` remains exactly one thin delegation to the injected
canonical `OperationEventStream.read_after` port. It owns no cursor, history,
validation, subscription, connection, buffering, or retry authority. Targeted
census found exactly three supervisor constructor sites and every site supplies
`event_stream=journal`; `OperationJournalRepository.read_after` remains the sole
durable replay implementation. The real-adapter replay proof covers an unknown
operation, bounded two-plus-one pages, repeated-page idempotence, monotonic
exclusive cursor advancement, caught-up state, and a fresh observer reading the
retained journal.

Independent verification passed 181 tests across the complete application and
persistence operations suites under `--noconftest`; Ruff, Ruff format check,
BasedPyright, and scoped diff hygiene all passed for the eight-file enlarged
surface. The campaign executor separately reported its current complete scoped
lane at 214 passed with the same static gates clean.

No implementation changes are required. The enlarged exact S23 boundary is
review-ready as one atomic delivery. Keep the plan row open and uncommitted for
the authorized executor to record and deliver.
