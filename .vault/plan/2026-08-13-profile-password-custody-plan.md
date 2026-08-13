---
tags:
  - '#plan'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_hash: 'sha256:b379d1c7e443246f8e30f1fb800235535f1b8e23c2cde96866018816285022b1'
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

## Steps

## Wave `W01` - custody substrate

Establish the only current-format profile custody primitives before lifecycle code can consume them; the session and transport waves depend on these invariants.

### Phase `W01.P01` - contract and taxonomy

Define strict current-format custody records, typed refusals, and storage ownership before any cryptographic or lifecycle implementation.

- [x] `W01.P01.S01` - Have Terra XHigh define the strict v1 custody records, typed refusals, password limits, and taxonomy ownership; `src/cadrumo/adapters/persistence/storage/custody/`.
- [x] `W01.P01.S02` - Have Sol Medium review the custody contract and taxonomy against the accepted hard-cutover constraints before cryptographic work starts; `src/cadrumo/adapters/persistence/storage/custody/`.

### Phase `W01.P02` - cryptography and filesystem publication

Implement supervised password wrapping, optional recovery, sentinels, capsules, journals, and exact pointer publication.

- [x] `W01.P02.S03` - Have Terra XHigh implement finite-grid Argon2id calibration and a supervised child with ready-before-secret, framed-DEK-only results, and parent sentinel proof; `src/cadrumo/adapters/persistence/storage/custody/`.
- [x] `W01.P02.S04` - Have Terra XHigh implement password and optional recovery envelopes, strict external recovery artifacts, DEK sentinel proof, and immutable capsule publication; `src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W01.P02.S05` - Have Terra XHigh implement custody and deletion journals, root-profile locks, no-follow inventory, legal-hold confirmation, receipts, pointer CAS, and atomic deletion; `src/cadrumo/application/user_profile/`.
- [ ] `W01.P02.S06` - Have Sol Medium jointly review KDF calibration and supervision, envelope and artifact AAD, capsule publication, journal recovery, and application-owned local deletion safety; `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/`.

## Wave `W02` - profile lifecycle and sessions

Move profile discovery, activation, session state, and handover onto the custody substrate; the transport wave consumes the resulting canonical capsule.

### Phase `W02.P03` - discovery and lifecycle ownership

Make committed UUID capsules the sole source for discovery, profile projection, and local lifecycle transitions.

- [ ] `W02.P03.S07` - Have Terra XHigh make the profile repository and aggregate project only committed UUID capsules through sole lifecycle writers; `src/cadrumo/application/user_profile/`.
- [ ] `W02.P03.S08` - Have Terra XHigh consolidate committed-marker discovery and the existence-only retired-path detector/refusal without legacy reads or keyring probes; `src/cadrumo/application/workflow/_profile_bucket_scan.py`.
- [ ] `W02.P03.S09` - Have Sol Medium review lifecycle discovery, projection provenance, selection, and local-delete authority before login integration; `src/cadrumo/application/user_profile/`.

### Phase `W02.P04` - login and session handover

Authenticate a candidate profile without disturbing the active one, then publish a bounded session only after success.

- [ ] `W02.P04.S10` - Have Terra XHigh authenticate profile B in a transaction-owned candidate namespace, clean it before swap on failure, and leave active A byte-for-byte intact; `src/cadrumo/application/user_profile/_login_session.py`.
- [ ] `W02.P04.S11` - Have Terra XHigh replace active and persisted sessions with bounded DEK sessions, atomic reference swap, B promotion, best-effort keyring, and ordered retirement; `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/_login_session.py`.
- [ ] `W02.P04.S12` - Have Sol Medium review candidate namespace cleanup, atomic in-process handover, B session promotion, keyring failure, post-swap recovery, and A non-resurrection; `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/adapters/persistence/storage/custody/`.

## Wave `W03` - restorative transport and operator surfaces

Rebuild restore and operator access around current capsules and explicit secret channels; removal depends on every consumer being moved.

### Phase `W03.P05` - archive and restore

Separate safe deterministic transport from custody-authorized password restore and explicit recovery restore.

- [ ] `W03.P05.S13` - Have Terra XHigh rebuild deterministic sealed archive transport framing without recovery.wrap, shared-master assumptions, or retired format parsing; `src/cadrumo/adapters/persistence/storage/bucket/`.
- [ ] `W03.P05.S14` - Have Terra XHigh implement password-only restore, explicit restore-recover lineage, exclusive recovery-artifact export-import, and new-identity portability; `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`.
- [ ] `W03.P05.S15` - Have Sol Medium review archive roots, hostile transport refusal, artifact export-import warnings and proof, restore publication, and rollback limits; `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`.

### Phase `W03.P06` - CLI and TUI authority

Expose canonical profile verbs and secret channels through typed action envelopes and truthful operator surfaces.

- [ ] `W03.P06.S16` - Have Terra XHigh expose canonical profile restore, restore-recover, and delete verbs through action envelopes and one-shot secrets-fd; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W03.P06.S17` - Have Terra XHigh update root bootstrap, TUI login, locales, and status projection to remove old environment and provider channels; `src/cadrumo/entrypoints/`.
- [ ] `W03.P06.S18` - Have Sol Medium review CLI and TUI secret handling, typed outcomes, bootstrap exemptions, and local-only operator guarantees; `src/cadrumo/entrypoints/cli/`.

## Wave `W04` - retire superseded custody

Remove every shared-master, provider-routing, recovery-mirror, and legacy-format surface after its consumers have moved; final proof depends on absence.

### Phase `W04.P07` - hard removal and negative audit

Remove shared-master custody and prove no retired path remains reachable or recognized.

- [ ] `W04.P07.S19` - Have Terra XHigh replace every direct MasterKeyProvider consumer with canonical per-profile custody and DEK sessions across storage, AEAT adapters, application owners, and CLI composition; `src/cadrumo/adapters/persistence/storage/{blob_store,crypto,envelope,secret_store}/; src/cadrumo/adapters/outbound/aeat/{auth,sede}/; src/cadrumo/application/{auth/_sessions.py,diagnostics.py,repair_integrity.py,user_profile/,workflow/_profile_health.py}; src/cadrumo/entrypoints/cli/`.
- [ ] `W04.P07.S20` - Have Terra XHigh delete retired provider, global recovery, raw-Argon, bootstrap, payload, locale, and legacy test surfaces after the replacement sweep; `src/cadrumo/adapters/persistence/storage/master_key/; src/cadrumo/adapters/persistence/storage/{__init__.py,_rotation.py,_kdf_bounds.py,errors.py}; src/cadrumo/application/{bucket_maintenance/,user_profile/}; src/cadrumo/entrypoints/cli/{__init__.py,_bootstrap_exempt.py,_config/,_config_payloads.py,tests/}; src/cadrumo/{core/_storage_taxonomy_locations.py,tests/master_key.py}`.
- [ ] `W04.P07.S21` - Have Sol Medium perform a negative architecture audit proving only an existence-only retired-path detector remains and no legacy custody route is reachable; `src/cadrumo/`.

## Wave `W05` - end-to-end proof

Prove the hard cutover with real local filesystem, subprocess, CLI, TUI, and read-only DEHu flows; this is the final safety and architecture gate.

### Phase `W05.P08` - real-system verification

Exercise the actual local system and read-only DEHu path, then complete an independent security architecture proof.

- [ ] `W05.P08.S22` - Have Terra XHigh add real filesystem and subprocess custody matrices for isolation, calibration, supervision, crash recovery, deletion, and destructive reset; `src/cadrumo/adapters/persistence/storage/custody/tests/`.
- [ ] `W05.P08.S23` - Have Terra XHigh run and codify real CLI, TUI, recovery-isolation, artifact, and live read-only DEHu routes without remote writes; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W05.P08.S24` - Have Sol Medium complete the final security and architecture proof against every accepted custody invariant and execution record; `.vault/audit/`.
- [ ] `W05.P08.S25` - After S24 proves the hard cutover, perform the explicitly authorized local-only destructive reset of the existing disposable retired/shared-master store through the new canonical application-owned profile deletion authority, capture journal and receipt evidence, re-enrol only current-format profiles, never read/adopt/migrate retired custody, never delete through raw filesystem or SQL, and perform no AEAT or external mutation; `src/cadrumo/application/user_profile/; .vault/exec/`.
