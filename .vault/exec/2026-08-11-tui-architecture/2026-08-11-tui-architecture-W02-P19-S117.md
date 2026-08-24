---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bfacd28302738923326a35a18e470a25d1f205a3a45df184c8340ffbcd83c7fc'
step_id: 'S117'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-operation-observation-adr]]"
---
# Pin each definition_contract_digest atomically with invocation identity and define one application-owned observation materialization port binding the current snapshot, anchor cursor, bounded history, progress-fold input, and resynchronization checkpoint

## Scope

- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/_registry.py`
- `src/cadrumo/application/operations/_supervisor.py`
- `src/cadrumo/adapters/persistence/operations/_journal.py`
- `src/cadrumo/adapters/persistence/operations/_journal_validation.py`
- canonical application facade and real tests

## Description

Pin the exact live public definition digest in the current-only private journal record and require that digest to reproduce before every invocation read, re-entry, response, or mutation. Define one application-owned atomic observation-read contract by composing the existing persisted snapshot and replay-page authorities with the sole progress fold checkpoint/input. Preserve exactly one initial journal creation door.

## Outcome

- `OperationPersistedSnapshot` is current schema v5 and requires `definition_contract_digest` beside invocation identity and request reference.
- `OperationSupervisor.submit` selects the registered public contract before custody acquisition and writes its digest in the same journal create transition.
- `OperationRegistry.lookup_public_contract` is the fail-closed per-definition lookup; uncomposed registries cannot submit.
- `_load_pinned_snapshot` is the single supervisor load path. It validates the live registry digest before `inspect`, `observe`, `detach`, `await_terminal`, replay, secret submission, pre-entry cancellation, cancellation acknowledgement, cleanup escalation, settlement, and reconciliation can return or mutate.
- `_advance` independently revalidates the pin before every generic lifecycle mutation. `respond` therefore refuses drift before consuming or committing the durable interaction.
- Persistence compare-and-swap refuses digest mutation.
- `_SnapshotJournalRepository.commit` only advances an existing journal. Its path-absent initial-create fallback and the tests/helpers that codified commit-as-create were deleted; `create` is the sole creation authority.
- `OperationObservationReader` returns one `OperationObservationMaterialization` containing the anchored current snapshot, canonical `OperationReplayPage`, and `OperationProgressFoldInput`.
- Materialization validation rejects unknown-operation pages, cross-identity or future-revision events, cursor-ahead rows, anchor drift, incomplete fold coverage, CAUGHT_UP pages that have not reached the anchor, and EXPIRED/COMPACTED pages without the exact restart-cursor progress checkpoint.
- No persistence observation adapter read was implemented; that remains S118. No public fold/projector was implemented; that remains S119.

## Verification

- Ruff over application and persistence operation packages â€” passed.
- Targeted `ty check` over changed production modules â€” passed.
- Remediation-focused real filesystem, encrypted operand, supervisor, replay, secret, lease and journal tests â€” 103 passed.
- Full operation-platform suite â€” 368 passed; the sole remaining failure is the independently known concurrent stale persistence-facade export expectation for the canonical secure-reference namespace.
- Adversarial drift tests cover start, inspect, observe, detach, replay, await-terminal, request-cancel, cancellation acknowledgement, cleanup escalation, secret submission, pre-entry secret cancellation, response-before-write, and reconciliation/terminal early-return gating. Every checked mutation retains byte-identical journal content.
- The absent-commit witness proves `commit(revision=0)` raises and creates no journal file.
- Observation witnesses refuse an impossible CAUGHT_UP cursor behind the anchor and compaction without the exact restart checkpoint.
- Post-edit Vaultspec RAG converged on one supervisor journal load, one pin validator, one operation create implementation, one advance-only commit implementation, one materialization, and one observation-reader port.
- Exact census found no `_commit_history` helper, no create-or-advance commit prose/branch, no direct supervisor journal load outside `_load_pinned_snapshot`, and no frontend snapshot/replay join.

## Notes

Current-only policy is delete-and-refuse: schemas 1 through 4 are rejected and no migration, compatibility reader, alias, bridge, fallback digest, or re-export module was introduced. Domain operation tests that still construct uncomposed registries remain an S122 production-composition prerequisite and correctly fail closed.
