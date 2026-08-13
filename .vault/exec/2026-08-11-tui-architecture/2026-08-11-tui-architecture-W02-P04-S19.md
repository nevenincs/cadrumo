---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7f2f9035f45ebf8abf414d191d02f7ecde846a5d2d01257bc338250a0bf42b18'
step_id: 'S19'
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
     The S19 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Implement durable owner lease acquisition, renewal, conflict refusal, expiry observation, exact-predecessor release, and expired-owner takeover evidence, and require operation journal commits to verify the exact current live lease while holding the same JournalRepositoryBase lock and ## Scope

- `src/cadrumo/adapters/persistence/operations/_lease.py`
- `src/cadrumo/adapters/persistence/operations/_journal.py`
- `and focused real-filesystem lease and journal tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement durable owner lease acquisition, renewal, conflict refusal, expiry observation, exact-predecessor release, and expired-owner takeover evidence, and require operation journal commits to verify the exact current live lease while holding the same JournalRepositoryBase lock

## Scope

- `src/cadrumo/adapters/persistence/operations/_lease.py`
- `src/cadrumo/adapters/persistence/operations/_journal.py`
- `and focused real-filesystem lease and journal tests`

## Description

- Persist strict versioned credential-free lease records beside operation snapshots under the canonical operation-journal root.
- Reuse the public `JournalRepositoryBase` path, lock, validation, and hardened atomic-write authority without adding a storage taxonomy or a second writer.
- Implement caller-clocked absent, active, and expired inspection; absent-only acquisition; conflict and expiry refusal; exact renewal; expired-owner takeover; and exact release.
- Return the S17-derived deterministic observation and transition evidence directly, leaving lease identity, tokens, clocks, and evidence derivation outside the adapter.
- Verify journal commits against the exact current active durable lease at the persisted caller timestamp while the existing snapshot compare-and-swap lock remains held.
- Cover persistence reload, raw-byte corruption refusal, byte-preserving rejection, concurrent acquisition, and the shared lock boundary with real filesystem processes.

## Outcome

`OperationLeaseFilesystemRepository` persists one current-or-absent lease state per operation under `operation-journals` and does not generate a time, token, owner, or evidence identity. Acquisition refuses a live owner as `CONFLICT` and an expired owner as `EXPIRED` without mutation. Exact compare-and-swap either renews a live predecessor or records a valid expired-owner takeover; mismatched or missing predecessors return `OWNER_LOST` without mutation. Exact release records absence atomically.

`OperationJournalRepository` now checks the supplied lease against the durable current state and requires it to remain active at `OperationPersistedSnapshot.updated_at`. The check, snapshot compare-and-swap, and atomic replacement execute under the identical `JournalRepositoryBase` sidecar lock without recursive acquisition. No persistence adapter facade was added because that is reserved for the following Step.

Independent review found and remediation closed a future-owner escape: journal authorization now enforces the full interval `acquired_at <= snapshot.updated_at < expires_at`. A planted real-filesystem mutation proves a lease acquired after the snapshot timestamp is refused without changing the existing journal bytes.

## Grounding

- Live code discovery: `uvx vaultspec-rag search "durable operation journal lease ownership exclusive file lock exact active lease" --type code --include-path "src/**" --prefer production` returned the operation journal commit, the S17 lease contracts, and `JournalRepositoryBase` as the three authoritative epicenters. It also surfaced profile-export locking as a constraint-shape analogue, not an operation-lease owner.
- Live vault discovery: `uvx vaultspec-rag search "W02 P04 S19 durable lease operation journal ownership expiry exact compare and swap" --type vault --doc-type adr,research,plan,exec,audit` returned the accepted plan, S17 and S18 execution records, and their review audits as the governing evidence. Those documents were read in full together with the accepted ADR and research record.
- The code index reported 233 unpublished sections, so `rg -n -C 3 "def exclusive_file_lock|class .*Lease|compare_and_swap\\(|OWNER_LOST|TAKEN_OVER|OperationLeaseRepository|JournalRepositoryBase" src/cadrumo -g '*.py'` confirmed the exact public lease port, its S17 evidence models, and the shared hardened journal substrate.
- Adjudication: S17 remains the only owner of lease identity, caller time, transition evidence, and result validation; this adapter only persists those models. S18 remains the sole snapshot/history/replay owner. `OperationLeaseStorage` reuses the same operation-journal root and `JournalRepositoryBase` lock rather than defining a taxonomy, lock, or atomic-writer parallel. The custody and profile-export sites have different domain records and no operation-port contract, so importing or adapting them would duplicate authority rather than reuse it.

## Verification

- `uv run pytest -q -n 0 src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - 31 passed in 9.78s after the full lease-activity interval remediation.
- `uv run ruff check src/cadrumo/adapters/persistence/operations/_lease.py src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - passed.
- `uv run ruff format --check src/cadrumo/adapters/persistence/operations/_lease.py src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - 4 files already formatted.
- `uv run basedpyright src/cadrumo/adapters/persistence/operations/_lease.py src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` - 0 errors, 0 warnings, 0 notes.
- `uvx vaultspec-core vault check all` - exit 0; 1,382 existing shared-corpus advisory warnings and no structural failure.

## Notes

The first focused adapter invocation exposed stale relative imports in the existing S18 journal test, so the test now uses its canonical absolute production imports. No production behavior was changed by that correction. Plan progress and all peer-owned work remain untouched.

