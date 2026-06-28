---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
---

# `cli-workflow-redesign` audit: state-architecture W01 close

Closing note for Wave 1 (UUID identity model) of the state-architecture
plan, plus the identity-coupled steps of Wave 3 (rename collapse,
name-as-id sweep) which landed in the same cutover.

## What landed

| Commit | Content |
|---|---|
| `1dd2abcf7` | single-segment profile-value secure-object key + `new_profile_id()` |
| `097af43b4` | UUID identity cutover, production layer (15 files) |
| `7fd870f45` | test layer updated for the cutover |
| `09f4add1b` | review-blocker fix: UUID-fed apoderado verbs; dead torn-bucket error removed |

Profiles now mint an immutable `str(uuid4())` identity at creation;
the operator name is a decoupled mutable `label`. Secure-object key
de-doubled to `user-profile:{uuid}`. Bucket + keystore directories,
manifest `bucket_id`, and the active-profile pointer are all keyed by
UUID. `rename` collapsed to a label-only update - roughly 150 lines of
directory-move / re-key / rollback machinery deleted, not bypassed.

## Verification

- Targeted suite (`domain/user_profile`, `application/user_profile`,
  `application/wizard`, `adapters/.../bucket`, `application/workflow`,
  `entrypoints/cli/_config`): 363 passed, 1 failed.
- The single failure - `test_every_cli_translation_resolves_in_every_locale`
  - is an unrelated parallel campaign's gap (8 missing
  `cli.config.repair.integrity_*` locale keys from in-flight
  `repair integrity` work). Isolated, attributed, not introduced by
  this wave. Handoff: the `repair integrity` campaign must scaffold
  those keys.
- Mandatory post-execution code review run. Verdict after remediation:
  the identity model, key de-doubling, rename collapse, scanner, and
  tests are sound and match the ADRs.

## Findings actioned

### B1 (blocker) - apoderado verbs missed by the name-as-id sweep

The four `config auth apoderado` verbs fed the active-profile UUID
into the now-label-based `read_profile_bucket`, crashing with
`AttributeError` on every active-profile invocation. The test suite
missed it (no apoderado happy-path coverage). Fixed in `09f4add1b`:
rerouted through the by-UUID resolver; a real happy-path test added.
Lesson: a label/UUID resolver split needs every caller audited, and
each operator-facing verb needs at least one happy-path test.

### M1 - dead `WorkspaceBucketTornError`

The torn-bucket idempotency case is obsolete under per-create UUID
minting. Class, export, and error-registry row removed in `09f4add1b`.

### M2 - missing service-level rename test

`ProfileLifecycleService.rename` was rewritten without a direct test.
`test_rename_updates_label_only` and a tombstone-refusal test added.

## Deferred

- `W03.S15` - the testimonial regression persona pass over the
  `profile create / rename / switch / delete / status` flows has not
  been run. It is carried into a later verification checkpoint.
