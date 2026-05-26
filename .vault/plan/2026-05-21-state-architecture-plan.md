---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-21'
tier: L3
related:
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
  - '[[2026-05-20-cli-state-architecture-research]]'
  - '[[2026-05-21-cli-testimonial-reference]]'
---

# `cli-workflow-redesign` plan: profile state-management architecture

The shared, evolving plan for the profile/workspace
state-architecture slice. It executes the accepted identity,
aggregate, and read-projection decisions listed in frontmatter.

Objective: a robust, verified, tested, industry-grade profile
management backend. Existing on-disk state is abandoned at cutover:
no migration, no compatibility window.

Wave gate: the registry drift gate and the CLI test suite must be
green before and after each wave; every wave lands real-behavior
roundtrip and anti-tautology tests for the boundaries it touches.

## Wave `W01` - UUID identity model

Source: UUID-identity ADR.

- [x] `W01.S01` - generate an immutable `profile_id` (UUIDv4) at profile creation; `profile record and BucketManifest`.
- [x] `W01.S02` - de-double the secure-object keys to `user-profile:{uuid}` and `user-profile-snapshot:{uuid}:{snapshot_id}`; `_repository.py`.
- [x] `W01.S03` - name the bucket directory (`_layout.py`) and keystore directory (`_keystore_paths.py`) by UUID; `BucketPointer`.
- [x] `W01.S04` - enforce display-name uniqueness among live profiles and permit tombstoned name reuse; `profile validation`.
- [x] `W01.S05` - add roundtrip and anti-tautology coverage for dual-field manifest and UUID-keyed secure object; `profile repository tests`.

## Wave `W02` - profile aggregate, repository, unit-of-work

Source: aggregate ADR.

- [x] `W02.S06` - introduce the `ProfileAggregate` typed model; `profile domain`.
- [x] `W02.S07` - make `ProfileRepository` the sole writer of profile physical stores; `profile persistence`.
- [x] `W02.S08` - implement cross-store unit-of-work for `create` and `delete`; `profile repository`.
- [x] `W02.S09` - run `verify_profile_integrity` on every `load`; `profile repository`.
- [x] `W02.S10` - add roundtrip and anti-tautology coverage for repository unit-of-work failures; `profile repository tests`.

## Wave `W03` - rename collapse, name-as-id sweep, legacy deletion

Source: UUID-identity ADR + aggregate ADR.

- [x] `W03.S11` - collapse `LifecycleService.rename` and CLI `config profile rename` to a label-only update; `profile lifecycle`.
- [x] `W03.S12` - route name-as-id call sites through `ProfileRepository`; `CLI command entry`.
- [x] `W03.S13` - read the display name from manifest `label`; `_profile_bucket_scan`.
- [x] `W03.S14` - delete legacy name-keyed code paths; `profile repository`.
- [x] `W03.S15` - re-run testimonial regression persona for `profile create / rename / switch / delete / status`; `CLI profile flows`.

## Wave `W04` - canonical state read-projection

Source: read-projection ADR.

- [x] `W04.S16` - introduce `OperatorStateProjection`; `application state`.
- [x] `W04.S17` - make `build_operator_state_projection` the single readiness producer; `application state`.
- [x] `W04.S18` - rewire operator-facing surfaces to consume the projection; `CLI overview/auth/modelo/verify`.
- [x] `W04.S19` - prove surface agreement with one fixture state; `projection tests`.

Follow-up - DONE (`21c994fb3`): the `WorkflowEngine`
`NO_PENDING_OBLIGATION` gate and the projection's
`pending_obligations` now draw from one shared producer,
`compute_obligation_schedule`, so the two can no longer diverge.
The gate keeps its own `next_deadline` and `(modelo, period)`
filtering; only the schedule source is unified. A gate/projection
agreement test in `test_engine.py` proves it.

## Wave `W05` - one state root and full verification

Source: UUID-identity ADR + aggregate ADR.

- [x] `W05.S20` - re-key auth token and lock filenames to the UUID prefix; `auth token store`.
- [x] `W05.S21` - confirm `AEAT_LOCAL_STORAGE_ROOT` roots every profile store end to end; `persona harness`.
- [x] `W05.S22` - run full CLI plus registry suite, cross-store integrity, and testimonial regression batch; `profile/auth/overview/verify surfaces`.

## Wave `W06` - tombstone lifecycle correctness

Source: the W05.S22 / W03.S15 testimonial regression audit. A
real-operator persona found `profile delete` tombstones a profile but
the tombstoned profile still leaked into the live surface: listed,
switchable, reported ready, and its name stayed reserved, violating
the identity ADR's tombstoned-name reuse constraint.

- [x] `W06.S23` - exclude tombstoned profiles from the live surface; `profile list/switch/show`.
- [x] `W06.S24` - reject manifest-record lifecycle drift and fail closed during delete; `profile integrity`.

## Tracking

| Wave | Intent | ADR | State |
|---|---|---|---|
| W01 | UUID identity model | identity | complete |
| W02 | aggregate + repository + unit-of-work | aggregate | complete |
| W03 | rename collapse + name-as-id sweep | identity + aggregate | complete |
| W04 | canonical read-projection | read-projection | complete |
| W05 | one state root + full verification | identity + aggregate | complete |
| W06 | tombstone lifecycle correctness | testimonial | complete |

## Audit cadence

Each wave closes with a `.vault/audit/` note recording what landed,
the test evidence, and any deferred finding. Findings become either a
fix-plus-roundtrip-test in the next wave or an explicit wontfix note:
never unactioned drift.
