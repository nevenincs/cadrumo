---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-21-state-architecture-w04-audit]]"
---

# `cli-workflow-redesign` audit: state-architecture W05 close

Closing note for Wave 5 (one state root) of the state-architecture
plan - the final structural wave.

## What landed

| Commit | Content |
|---|---|
| `be61219cb` | root the auth token/lock directory under `aeat_local_storage_root` |
| (this close) | register the W02 pointer-restore write sites in the persistence-policy inventory |

`aeat_token_dir` previously defaulted to a repo-root `.tokens/`
directory outside `aeat_local_storage_root`, so the isolation
contract that tests and the persona harness depend on was silently
false. A `model_validator(mode="after")` now derives
`<aeat_local_storage_root>/tokens` when the field is not explicitly
set; an explicit `AEAT_TOKEN_DIR` override still wins. `browser/_factory.py`
was found to already key on the bucket UUID - only a misleadingly
named local variable was corrected.

## One-state-root inventory

Every profile store now resolves under `aeat_local_storage_root`:
bucket directory, manifest, secure DB, active-profile pointer,
per-bucket lockfile, auth token files, auth lock files, browser
storage-state. The state-architecture research's consideration 7
("one state root") is satisfied.

## Finding actioned: persistence-policy inventory

`test_production_file_write_inventory_is_reviewed` flagged two
unregistered production file-write sites - `_restore_pointer_text`
(`_profile_repository.py`) and `restore_active_profile_pointer`
(`_orchestration.py`), both added by the W02 cold-start rollback.
They are legitimate (each restores the plaintext active-profile
pointer, bucket UUID only, during a failed-create rollback) and are
now registered with justifications. This was W02 debt surfaced during
W05 verification - actioned, not deferred.

## Verification

- `src/aeat/core` + `application/auth` + `adapters`: 1927 passed,
  4 skipped, 0 failed (after the inventory-test fix).
- New `test_token_dir_state_root.py`: 5 passed.
- Full `entrypoints/cli` tree: 8 failures, every one foreign-WIP
  attributable - the 3 long-standing (`test_workflow_surface.py` x2,
  `test_backend_boundary.py` x1) plus 5 in `test_profile_lifecycle_verbs.py`
  proven to be active-profile state-bleed FROM the foreign WIP in
  `test_workflow_surface.py` (excluding that file makes all 5 vanish).

## Deferred

- `W05.S22` - the testimonial regression persona pass over
  `profile` / `auth` / `overview` flows (also covers the deferred
  `W03.S15`). It is the campaign's final verification and runs next.
- The CLI failures close when the owning campaigns commit their WIP.
