---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b9220a268f2dca64eb55140594b8ad4082d9f571b8ae202c22616d46af26d813'
step_id: 'S18'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Implement the operation lifecycle journal over the existing atomic journal substrate and ## Scope

- `src/cadrumo/adapters/persistence/operations/_journal.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the operation lifecycle journal over the existing atomic journal substrate

## Scope

- `src/cadrumo/adapters/persistence/operations/_journal.py`
- Public two-hop `JournalRepositoryBase` facade promotion.
- Operation-journal storage taxonomy, path grammar, and durable compatibility declaration.
- Real-filesystem adapter and canonical boundary tests.

## Description

- Reuse `JournalRepositoryBase` through the public application and operations facades.
- Declare the fixed root-scoped `operation-journals` location and exact per-operation JSON grammar without disturbing the concurrent profile-custody taxonomy additions.
- Enroll `operation_journal` as a durable persisted format.
- Persist the latest credential-free snapshot and complete ordered history in one typed file under one repository lock.
- Refuse repeated creation, stale revision, non-unit revision advance, lease mismatch, identity/reference/start-time drift, terminal advance, and discontinuous event append before replacement.

## Outcome

The filesystem adapter now implements the application journal port without importing private application modules or duplicating atomic-write mechanics. Initial creation requires expected and stored revision zero. An existing revision `r` accepts only expected `r` and successor `r + 1`; all comparison and transition checks execute while the canonical repository lock is held. The single file stores the latest `OperationPersistedSnapshot` plus the complete typed event history, so advancing state cannot discard replay evidence. A fresh repository instance reloads the same credential-free state, and refusal tests prove the prior bytes remain unchanged.

`OperationJournalRepository` now also implements `OperationEventStream.read_after` from that complete retained history. Replay validates its cursor and limit before filesystem access, returns `unknown_operation` only for an absent record, returns an exclusive bounded `page` with an exact next cursor when retained events exist, and returns `caught_up` unchanged otherwise. The adapter does not claim expiry or compaction because this storage policy retains history. Repeating the same request returns the same page.

The private typed record now refuses cross-revision corruption: every history event must have the stored identity; sequences must begin at one and remain globally contiguous; timestamps must not decrease; revision groups must advance in unit order and end at the latest snapshot revision; terminal events may occur only at the complete-history tail; and the final history suffix must exactly equal the latest snapshot event batch. Creation permits an empty cursor-zero history or events beginning at sequence one. The supplied lease remains correlation-only: it must name the operation being written, without deciding owner, token, expiry, renewal, or takeover policy.

Focused verification:

- `uv run ruff check src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/application/__init__.py src/cadrumo/application/operations/__init__.py src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py src/cadrumo/core/_storage_taxonomy.py src/cadrumo/core/_storage_taxonomy_locations.py src/cadrumo/core/compatibility_lifecycle.py` - passed.
- `uv run pytest -q -n 0 src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py src/cadrumo/core/tests/test_storage_taxonomy.py src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py` - 51 passed in 0.62 seconds.
- `uv run basedpyright src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/application/__init__.py src/cadrumo/application/operations/__init__.py` - 0 errors, 0 warnings, 0 notes.
- `uv run ruff check src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - passed.
- `uv run pytest -q -n 0 src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - 9 passed in 1.95 seconds after correcting the new non-package test module to canonical absolute imports.
- `uv run basedpyright src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - 0 errors, 0 warnings, 0 notes.
- `uvx vaultspec-core vault check all` - exit 0; structural checks passed with 1,365 advisory shared-corpus warnings and no closure error.

## Notes

Live code and vault semantic searches converged on the canonical per-file `JournalRepositoryBase`, D5/D10 durability requirements, the storage taxonomy/path registry, and compatibility lifecycle authority. The registry and secure-reference store remain separate authorities: S18 persists only the opaque request digest and safe facts already defined by S17; later supervisor composition resolves the runtime typed operand. The interrupted first implementation overwrote prior event batches on revision advance; verifier audit corrected the canonical representation to a private one-file envelope containing current snapshot plus full ordered history. No codec, private import, inline request payload, `Any`, mapping fallback, adapter-owned lease policy, or duplicate atomic writer was added.

The replay remediation remains within S18: it exposes only current retained event history and does not introduce subscriber, retention, compaction, or lease-authority policy owned by later steps.
