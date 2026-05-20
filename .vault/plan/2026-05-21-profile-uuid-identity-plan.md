---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-21'
tier: L3
related:
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
---

# `cli-workflow-redesign` plan: profile UUID-identity migration

Executes `[[2026-05-21-profile-uuid-identity-adr]]`. Evolving tracking
document - step state is updated as waves land. Execution does not
begin until the ADR is `accepted` and this plan is approved.

Gate before each wave: the registry drift gate and the CLI test suite
must be green; cross-store integrity verified; a testimonial
regression persona re-runs the `profile` flows after W3.

## Wave `W01` - identity model behind the migration

Introduce the UUID identity without yet cutting over on-disk state.
New writes carry both fields; readers tolerate both.

- [ ] `W01.S01` - add immutable `profile_id` (UUIDv4) generation at
  profile creation; add `label` (display name) as a distinct field on
  `UserProfileRecord` and `BucketManifest`.
- [ ] `W01.S02` - de-double the secure-object keys:
  `user-profile:{uuid}` and `user-profile-snapshot:{uuid}:{snapshot_id}`
  in `_repository.py`; keep the old key readable ONLY for the
  migration command's use, nowhere else.
- [ ] `W01.S03` - name-uniqueness validator: display names unique
  among live profiles, case-insensitive; tombstoned names reusable.
- [ ] `W01.S04` - roundtrip + anti-tautology tests for the dual-field
  record and the UUID-keyed secure object.

## Wave `W02` - the one-time forward migration command

- [ ] `W02.S05` - `aeat config migrate-profile-uuid`: inventory every
  bucket, generate a UUID per bucket, persist the `name -> uuid` map
  before any mutation.
- [ ] `W02.S06` - single-SQLite-transaction row re-key; manifest
  rewrite (`bucket_id`=uuid, `label`=name); bucket + keystore
  directory rename; pointer rewrite.
- [ ] `W02.S07` - crash-recovery: detect the degraded state (UUID
  keys in a name-named directory) and make the command idempotent /
  re-runnable.
- [ ] `W02.S08` - real-behavior test: a name-keyed fixture bucket
  migrates to a healthy UUID-keyed profile; a simulated mid-migration
  crash is repaired by a re-run.

## Wave `W03` - cut over: collapse `rename`, sweep name-as-id sites

- [ ] `W03.S09` - collapse `LifecycleService.rename` and the CLI
  `config profile rename` handler to a label-only field update;
  delete the directory-move / re-key / rollback machinery.
- [ ] `W03.S10` - sweep the 22 name-as-id call sites (per the
  discovery reference blast-radius list): `_layout.py`,
  `_manifest.py`, `_bucket_pointer.py`, `_profile_bucket_scan.py`,
  `_orchestration.py` 1:1 convention, `_secure_objects_for_bucket`,
  `_keystore_paths.py`, the 8 CLI entrypoints.
- [ ] `W03.S11` - `_profile_bucket_scan` reads the display name from
  the manifest `label`, never the directory name.
- [ ] `W03.S12` - drop the old-key read path entirely; new code reads
  only `user-profile:{uuid}`.
- [ ] `W03.S13` - testimonial regression persona re-runs the
  `profile create / rename / switch / delete / status` flows.

## Wave `W04` - auth token/lock filenames

- [ ] `W04.S14` - re-key the 5 auth token/lock filename sites to the
  UUID prefix; orphaned token files force one re-auth (documented,
  not data loss); lock files are deleted (TTL handles staleness).
- [ ] `W04.S15` - confirm `AEAT_LOCAL_STORAGE_ROOT` (and the token
  dir) isolation holds end to end - the persona harness depends on it.

## Tracking

| Wave | Intent | State |
|---|---|---|
| W01 | identity model | not started |
| W02 | migration command | not started |
| W03 | cutover + call-site sweep | not started |
| W04 | auth token/lock filenames | not started |

## Open questions for the architect

- Confirm the breaking one-time migration is acceptable (no dual-key
  compatibility window) - the ADR assumes pre-1.0 local-first state.
- Should `migrate-profile-uuid` run automatically on first post-upgrade
  invocation, or only on explicit operator command? The ADR proposes
  explicit; auto-run is a UX call.
