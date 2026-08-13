---
tags:
  - '#plan'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_hash: 'sha256:772946115f635efdffa9e5b75607daafb1c1ecdc811f38b3d95a6411554f954a'
tier: L3
related:
  - '[[2026-08-13-profile-password-custody-research]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-08-13-auth-certificate-lifecycle-successor-adr]]'
  - '[[2026-08-13-cli-action-envelope-successor-adr]]'
  - '[[2026-08-13-profile-bucket-lifecycle-successor-adr]]'
  - '[[2026-08-13-profile-disaster-operations-successor-adr]]'
  - '[[2026-08-13-profile-portability-successor-adr]]'
  - '[[2026-08-13-profile-session-lifecycle-successor-adr]]'
  - '[[2026-08-13-profile-state-aggregate-successor-adr]]'
  - '[[2026-08-13-recovery-mnemonic-presentation-successor-adr]]'
  - '[[2026-08-13-sealed-archive-transport-successor-adr]]'
  - '[[2026-08-13-secure-storage-hardening-successor-adr]]'
---

# `profile-password-custody` plan

Hard-cut over profile unlock to password-wrapped per-profile custody, removing every shared-master and legacy authority while preserving only current-format, locally durable recovery paths.

## Description

This L3 plan executes the accepted custody roll-up and its ten successor decisions. Wave W01 defines the current-format custody contract and capsule transaction substrate. Wave W02 makes committed capsules, lifecycle projection, and sessions consume that substrate. Wave W03 rebuilds restorative transport and the CLI/TUI authority surface. Wave W04 deletes the retired provider and all legacy recognition. Wave W05 proves the complete cutover using real local process and operator routes. Work occurs only in the main worktree with its normal shared index: no alternate index, lock workaround, or product-storage mutation during implementation. The existing disposable store is reset only after the new cutover is implemented and validated. Normal operations remain local and perform no AEAT or other remote write.

## Steps

## Wave `W01` - custody substrate

Establish the only current-format profile custody primitives before lifecycle code can consume them; the session and transport waves depend on these invariants.

### Phase `W01.P01` - contract and taxonomy

Define strict current-format custody records, typed refusals, and storage ownership before any cryptographic or lifecycle implementation.

- [ ] `W01.P01.S01` - Have Terra XHigh define the strict v1 custody records, typed refusals, password limits, and taxonomy ownership; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W01.P01.S02` - Have Sol Medium review the custody contract and taxonomy against the accepted hard-cutover constraints before cryptographic work starts; `src/cadrumo/adapters/persistence/storage/custody/`.

### Phase `W01.P02` - cryptography and filesystem publication

Implement supervised password wrapping, optional recovery, sentinels, capsules, journals, and exact pointer publication.

- [ ] `W01.P02.S03` - Have Terra XHigh implement the bounded Argon2id child-worker and Windows/POSIX supervision adapter with ready handshake; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W01.P02.S04` - Have Terra XHigh implement password and recovery envelopes, DEK sentinel proof, and immutable capsule publication; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W01.P02.S05` - Have Terra XHigh implement custody journals, crash preflight, exact pointer compare-and-swap, and local create-delete primitives; `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`.
- [ ] `W01.P02.S06` - Have Sol Medium jointly review KDF supervision, envelope AAD, capsule publication, journal recovery, and deletion safety; `src/cadrumo/adapters/persistence/storage/custody/`.

## Wave `W02` - profile lifecycle and sessions

Move profile discovery, activation, session state, and handover onto the custody substrate; the transport wave consumes the resulting canonical capsule.

### Phase `W02.P03` - discovery and lifecycle ownership

Make committed UUID capsules the sole source for discovery, profile projection, and local lifecycle transitions.

- [ ] `W02.P03.S07` - Have Terra XHigh make the profile repository and aggregate project only committed UUID capsules through sole lifecycle writers; `src/cadrumo/application/user_profile/`.
- [ ] `W02.P03.S08` - Have Terra XHigh consolidate current-capsule discovery and remove duplicate profile scans and manifest-authority reads; `src/cadrumo/application/workflow/_profile_bucket_scan.py`.
- [ ] `W02.P03.S09` - Have Sol Medium review lifecycle discovery, projection provenance, selection, and local-delete authority before login integration; `src/cadrumo/application/user_profile/`.

### Phase `W02.P04` - login and session handover

Authenticate a candidate profile without disturbing the active one, then publish a bounded session only after success.

- [ ] `W02.P04.S10` - Have Terra XHigh implement candidate-profile authentication before active-reference swap and preserve the prior active session on failure; `src/cadrumo/application/user_profile/_login_session.py`.
- [ ] `W02.P04.S11` - Have Terra XHigh replace active bucket and persisted session handling with the bounded per-profile DEK session model; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W02.P04.S12` - Have Sol Medium review the login handover, session revocation, keyring-optional acceleration, and current-profile preservation invariant; `src/cadrumo/application/user_profile/_login_session.py`.

## Wave `W03` - restorative transport and operator surfaces

Rebuild restore and operator access around current capsules and explicit secret channels; removal depends on every consumer being moved.

### Phase `W03.P05` - archive and restore

Separate safe deterministic transport from custody-authorized password restore and explicit recovery restore.

- [ ] `W03.P05.S13` - Have Terra XHigh rebuild sealed archive transport framing without recovery.wrap, shared-master assumptions, or retired format recognition; `src/cadrumo/adapters/persistence/storage/bucket/`.
- [ ] `W03.P05.S14` - Have Terra XHigh implement password-only restore, explicit restore-recover, and separate new-identity portability import; `src/cadrumo/application/bucket_maintenance/`.
- [ ] `W03.P05.S15` - Have Sol Medium review archive content roots, hostile transport refusal, recovery-artifact boundaries, restore publication, and rollback limits; `src/cadrumo/application/bucket_maintenance/`.

### Phase `W03.P06` - CLI and TUI authority

Expose canonical profile verbs and secret channels through typed action envelopes and truthful operator surfaces.

- [ ] `W03.P06.S16` - Have Terra XHigh expose canonical profile restore, restore-recover, and delete verbs through action envelopes and one-shot secrets-fd; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W03.P06.S17` - Have Terra XHigh update root bootstrap, TUI login, locales, and status projection to remove old environment and provider channels; `src/cadrumo/entrypoints/`.
- [ ] `W03.P06.S18` - Have Sol Medium review CLI and TUI secret handling, typed outcomes, bootstrap exemptions, and local-only operator guarantees; `src/cadrumo/entrypoints/cli/`.

## Wave `W04` - retire superseded custody

Remove every shared-master, provider-routing, recovery-mirror, and legacy-format surface after its consumers have moved; final proof depends on absence.

### Phase `W04.P07` - hard removal and negative audit

Remove shared-master custody and prove no retired path remains reachable or recognized.

- [ ] `W04.P07.S19` - Have Terra XHigh migrate every MasterKeyProvider consumer to the canonical per-profile custody and DEK session interfaces; `src/cadrumo/`.
- [ ] `W04.P07.S20` - Have Terra XHigh delete the master_key provider family, global recovery/config routes, raw Argon paths, and all supporting legacy tests; `src/cadrumo/adapters/persistence/storage/master_key/`.
- [ ] `W04.P07.S21` - Have Sol Medium perform a negative architecture audit proving no shared-master, AUTO, fallback, recovery mirror, legacy reader, or dual format remains; `src/cadrumo/`.

## Wave `W05` - end-to-end proof

Prove the hard cutover with real local filesystem, subprocess, CLI, TUI, and read-only DEHu flows; this is the final safety and architecture gate.

### Phase `W05.P08` - real-system verification

Exercise the actual local system and read-only DEHu path, then complete an independent security architecture proof.

- [ ] `W05.P08.S22` - Have Terra XHigh add real filesystem and subprocess custody-matrix verification for isolation, crash recovery, KDF limits, and destructive reset; `src/cadrumo/adapters/persistence/storage/custody/tests/`.
- [ ] `W05.P08.S23` - Have Terra XHigh run and codify real CLI and TUI custody routes plus the live read-only DEHu verification route without remote writes; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W05.P08.S24` - Have Sol Medium complete the final security and architecture proof against every accepted custody invariant and execution record; `.vault/audit/`.

## Parallelization

Waves are strictly serial. Within a coding phase, independent file areas may be owned by separate Terra XHigh executors only after the preceding serial Sol Medium architecture-review step and only when their current diffs do not overlap. Every coding handoff re-runs semantic discovery, reads the live owning files, confirms symbols and consumers with exact search, and preserves concurrent work. Sol Medium reviews are hard gates: no downstream Wave begins until its immediately preceding review Step is completed without unresolved critical or high finding. The W05 proof steps run only after W04 deletion and its negative audit close.

## Verification

Each coding Step uses real behavior tests that import and exercise production code, never test doubles, monkeypatches, fake implementations, or business logic in tests. The execution record proves the exact current paths and removal checks. Required gates include current-format envelope and sentinel authentication, password-only unlock independent of missing recovery/keyring/projection state, supervised child KDF limits, atomic capsule and pointer crash recovery, candidate-login preservation, archive and restore refusal of retired formats, local-only delete receipts, and absence scans for shared-master/AUTO/fallback paths. W05 runs real filesystem and subprocess cases plus exact CLI and TUI routes; it also runs the existing DEHu verification path in read-only mode only and explicitly proves no AEAT or other remote write. The shared semantic service is intentionally compute-quiesced during planning, so fallback-search absence is never treated as proof; execution must use a healthy mandated discovery path before edits. Plan completion requires all 24 Steps, their matching exec records, all Sol Medium gates, feature-scoped checks, and a final architecture/security review.
