---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7b30a55e640f4ba3fa750357754ef2c75e2dbe13fa210fcd41d33f3c3644a67c'
step_id: 'S168'
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
     The S168 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Replace the strict active-profile pointer record and IO owner with one atomic absent-or-selected observation/current-coordinate contract that persists its monotonic transition revision under the canonical custody-root lock, promote the core record/coordinate surface and sole user-profile transaction through their canonical facades, atomically migrate every exact direct reader and transaction consumer, and prove idempotence, cross-process A -> B -> A, restore/clear lineage, and zero dual reader/writer, compatibility reader, shim, alias, fallback, or re-export bridge and ## Scope

- `src/cadrumo/core/_bucket_pointer.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`
- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/user_profile/_login_session.py`
- `src/cadrumo/application/user_profile/_lifecycle.py`
- `src/cadrumo/application/user_profile/_custody_service.py`
- `src/cadrumo/application/user_profile/_custody_repository.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_delete.py`
- `and focused pointer-record/facade/direct-reader/transaction concurrency tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the strict active-profile pointer record and IO owner with one atomic absent-or-selected observation/current-coordinate contract that persists its monotonic transition revision under the canonical custody-root lock, promote the core record/coordinate surface and sole user-profile transaction through their canonical facades, atomically migrate every exact direct reader and transaction consumer, and prove idempotence, cross-process A -> B -> A, restore/clear lineage, and zero dual reader/writer, compatibility reader, shim, alias, fallback, or re-export bridge

## Scope

- `src/cadrumo/core/_bucket_pointer.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`
- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/user_profile/_login_session.py`
- `src/cadrumo/application/user_profile/_lifecycle.py`
- `src/cadrumo/application/user_profile/_custody_service.py`
- `src/cadrumo/application/user_profile/_custody_repository.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_delete.py`
- `and focused pointer-record/facade/direct-reader/transaction concurrency tests`

## Description

- Replace the selected-only pointer payload with a strict v2 absent-or-selected
  record carrying its persisted `transition_revision`.
- Make the custody-root transaction the sole production transition authority and
  retain clear operations as absent tombstones.
- Move direct consumers, durable reset and handover witnesses, and public facade
  exports to the canonical observation and coordinate.
- Delete the duplicate custody snapshot reader, byte-CAS facade, byte restore and
  unlink clear APIs, and compatibility reader paths.
- Add focused lineage, spawned ABA, no-follow, idempotence, facade fixed-point,
  v1-rejection, and consumer-coordinate coverage.

## Outcome

Implementation is in `d64845fbf1a`; the step remains open while the required
follow-up verification fixes and shared-worktree import validation complete.

## Notes

- `d64845fbf1a` landed before the final verification pass. A transparent
  follow-up commit will contain only the test/static corrections identified by
  that pass and this execution/plan closure material; shared history is not
  rewritten.
- The `filing/_review.py` and `flows/_definition.py` changes bundled in
  `d64845fbf1a` are hashing refactors, not pointer-coordinate consumers. They
  are recorded here as an accidental scope sweep for separate review; this step
  neither depends on nor extends them.
