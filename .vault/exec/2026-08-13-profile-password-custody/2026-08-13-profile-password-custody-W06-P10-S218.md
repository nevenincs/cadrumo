---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ff4c7b0eb366d86ebca4c9263c3838b912114a8808cb0058294f591ba0a642fe'
step_id: 'S218'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S218 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Confirm recovery artifacts remain external restore proofs only, remove any API or prose that permits later enrollment or treats a missing creation wrapper as current-format success, and retain password login without recovery reads and ## Scope

- `src/cadrumo/application/user_profile/_recovery_custody.py and src/cadrumo/application/user_profile/_capsule_restore.py and src/cadrumo/application/user_profile/_custody_ports.py and src/cadrumo/adapters/persistence/storage/custody/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm recovery artifacts remain external restore proofs only, remove any API or prose that permits later enrollment or treats a missing creation wrapper as current-format success, and retain password login without recovery reads

## Scope

- `src/cadrumo/application/user_profile/_recovery_custody.py and src/cadrumo/application/user_profile/_capsule_restore.py and src/cadrumo/application/user_profile/_custody_ports.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Make the normal archive recovery slot permanently empty and reject non-empty recovery cargo.
- Remove recovery reads from the shared capsule-source reader and recovery installation from both restore authorities.
- Require creation callers to supply recovery while removing the restore-time recovery writer.
- Replace the ambiguous enrollment facade with an explicitly creation-only minting door.
- Prove real password login succeeds with missing and malformed recovery material.
- Migrate direct lifecycle test publishers through a secret-wiping creation fixture.

## Outcome

- Normal backup and password restore do not parse recovery; damaged recovery cannot block either operation.
- Recovery artifacts remain identity-bound proof for explicit artifact restore and never become enrolled recovery in the destination.
- `ProfileCapsuleLifecycle.create` has no password-only signature and `restore` has no recovery-envelope argument.
- The old public `enroll_profile_recovery` and raw material-construction facade exports are gone; the remaining public mint is named and documented for creation only.
- Core application, storage, lifecycle, isolation, archive, restore, login-independence, and TUI reachability suites passed 56 tests. Ancillary migrated fixture suites passed 28 relevant tests; two unrelated operator-output schema failures remain characterized.
- Scoped Ruff passed outside an unrelated concurrently edited facade file; scoped ty passed for the production boundary and new login proof.

## Notes

- Formal review initially found that the shared source reader still parsed recovery and that lower lifecycle signatures retained forbidden optional/installing paths. Both findings were corrected before close.
- Two pre-existing operator-output capability/schema assertions fail independently of custody and were not changed.
- The shared worktree contains concurrent edits in the application facade and several migrated fixture files; only S218 hunks are intended for capture.
