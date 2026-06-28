---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
tier: L3
related:
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - "[[2026-05-20-cli-state-architecture-research]]"
  - "[[2026-05-21-cli-testimonial-reference]]"
---

# `cli-workflow-redesign` plan: profile state-management architecture

The shared, evolving plan for the profile/workspace state-architecture
slice. It executes three accepted ADRs:

- `[[2026-05-21-profile-uuid-identity-adr]]` - UUID identity, decoupled
  label, clean cutover (no migration).
- `[[2026-05-21-profile-state-aggregate-adr]]` - one aggregate, one
  repository, cross-store unit-of-work, one state root.
- `[[2026-05-21-state-read-projection-adr]]` - one canonical state
  read-projection consumed by every operator-facing surface.

These three ADRs are one slice: the testimonial cluster triaged in
`[[2026-05-20-cli-state-architecture-research]]` is a single
architecture problem (fragmented state, identity coupled to location,
no transaction boundary, every reader re-deriving). The
ledger-to-calculation bridge (research consideration 5) is **out of
scope** for this plan and tracked separately by the architect.

Objective: a robust, verified, tested, industry-grade profile
management backend. Existing on-disk state is abandoned at cutover -
no migration, no compatibility window.

Wave gate: the registry drift gate and the CLI test suite must be
green before and after each wave; every wave lands real-behavior
roundtrip and anti-tautology tests for the boundaries it touches.

## Wave `W01` - UUID identity model

Source: UUID-identity ADR.

- [x] `W01.S01` - generate an immutable `profile_id` (UUIDv4) at
  profile creation; add `label` (display name) as a distinct mutable
  field on the profile record and `BucketManifest`; `bucket_id`
  becomes the UUID.
- [x] `W01.S02` - de-double the secure-object keys to
  `user-profile:{uuid}` and
  `user-profile-snapshot:{uuid}:{snapshot_id}` in `_repository.py`.
- [x] `W01.S03` - bucket directory (`_layout.py`) and keystore
  directory (`_keystore_paths.py`) named by UUID; `BucketPointer`
  stores the UUID.
- [x] `W01.S04` - name-uniqueness validator: display names unique
  among live profiles, case-insensitive; tombstoned names reusable.
- [x] `W01.S05` - roundtrip + anti-tautology tests for the
  dual-field manifest and the UUID-keyed secure object.

## Wave `W02` - profile aggregate, repository, unit-of-work

Source: aggregate ADR.

- [x] `W02.S06` - `ProfileAggregate` typed model (identity, label,
  manifest fields, secure record, lifecycle state).
- [x] `W02.S07` - `ProfileRepository`
  (`create`/`load`/`save`/`delete`/`list`) as the sole writer of
  profile physical stores.
- [x] `W02.S08` - cross-store unit-of-work for `create` and `delete`:
  staged filesystem, transactional SQLite commit, pointer last,
  rollback / detectable-garbage on failure.
- [x] `W02.S09` - `verify_profile_integrity` read-time validator
  generalising `assess_active_profile_health`; run on every `load`.
- [x] `W02.S10` - roundtrip + anti-tautology tests for the
  repository unit-of-work, including a simulated mid-`create`
  failure that must leave no half-live profile.

## Wave `W03` - rename collapse, name-as-id sweep, legacy deletion

Source: UUID-identity ADR + aggregate ADR.

- [x] `W03.S11` - collapse `LifecycleService.rename` and CLI
  `config profile rename` to a label-only field update; delete the
  directory-move / re-key / rollback machinery.
- [x] `W03.S12` - sweep the 22 name-as-id call sites (per the
  discovery reference) to route through `ProfileRepository`; CLI
  resolves `name -> uuid` via the manifest scan at command entry.
- [x] `W03.S13` - `_profile_bucket_scan` reads the display name from
  the manifest `label`, never the directory name.
- [x] `W03.S14` - delete the legacy name-keyed code paths entirely;
  no dual-key read path remains.
- [ ] `W03.S15` - testimonial regression persona re-runs the
  `profile create / rename / switch / delete / status` flows.

## Wave `W04` - canonical state read-projection

Source: read-projection ADR.

- [x] `W04.S16` - `OperatorStateProjection` typed model (active
  profile + health, auth readiness, workspace summary, per-modelo
  readiness, pending obligations).
- [x] `W04.S17` - `build_operator_state_projection` as the single
  producer; each readiness value computed exactly once.
- [x] `W04.S18` - rewire `overview`, `auth status`, `auth test`,
  `modelo readiness`, `verify` to consume the projection; delete
  their bespoke per-surface state assembly.
- [x] `W04.S19` - tests proving the surfaces agree: one fixture
  state, every surface reports the same readiness and counts.

Follow-up - DONE (`21c994fb3`): the `WorkflowEngine`
`NO_PENDING_OBLIGATION` gate and the projection's `pending_obligations`
now draw from one shared producer, `compute_obligation_schedule`, so
the two can no longer diverge. The gate keeps its own `next_deadline`
/ `(modelo, period)` filtering; only the schedule source is unified.
A gate/projection agreement test in `test_engine.py` proves it.

## Wave `W05` - one state root and full verification

Source: UUID-identity ADR + aggregate ADR.

- [x] `W05.S20` - re-key auth token/lock filenames to the UUID
  prefix and relocate the token/lock directory under
  `AEAT_LOCAL_STORAGE_ROOT`.
- [x] `W05.S21` - confirm `AEAT_LOCAL_STORAGE_ROOT` roots every
  profile store end to end - the persona harness depends on it.
- [ ] `W05.S22` - full CLI + registry suite green; cross-store
  integrity verified; testimonial regression batch across the
  `profile`, `auth`, `overview`, and `verify` surfaces.

## Wave `W06` - tombstone lifecycle correctness

Source: the W05.S22 / W03.S15 testimonial regression
(`[[2026-05-21-state-architecture-testimonial-regression-audit]]`).
A real-operator persona found `profile delete` tombstones a profile
but the tombstoned profile still leaked into the live surface -
listed, switchable, reported ready, and its name stayed reserved
(violating the identity ADR's "tombstoned names reusable").

- [x] `W06.S23` - exclude tombstoned profiles from the live surface:
  `list` omits them, `switch` refuses them, `show` reflects the
  tombstoned status, name and tax-id uniqueness consider only live
  profiles. A plaintext `status` marker on `BucketManifest` lets the
  manifest scan filter without decryption.
- [x] `W06.S24` - close the denormalization drift: `verify_profile_integrity`
  rejects a manifest status that disagrees with the record status,
  and `delete` writes the manifest mirror before the record tombstone
  so a crashed delete fails closed.

## Tracking

| Wave | Intent | ADR | State |
|---|---|---|---|
| W01 | UUID identity model | identity | complete |
| W02 | aggregate + repository + unit-of-work | aggregate | complete |
| W03 | rename collapse + name-as-id sweep | identity + aggregate | complete (S15 testimonial regression pending) |
| W04 | canonical read-projection | read-projection | complete |
| W05 | one state root + full verification | identity + aggregate | complete |
| W06 | tombstone lifecycle correctness | testimonial | complete |

## Audit cadence

Each wave closes with a `.vault/audit/` note recording what landed,
the test evidence, and any deferred finding. Findings become either a
fix-plus-roundtrip-test in the next wave or an explicit wontfix note -
never unactioned drift.
