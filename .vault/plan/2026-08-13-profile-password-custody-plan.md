---
tags:
  - '#plan'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-14'
body_hash: 'sha256:cea182950885471b6f296b01b1a68273c4f306923f316284f1f01970e301848c'
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
- [x] `W01.P02.S05` - Have Terra XHigh implement custody and deletion journals, root-profile locks, no-follow inventory, legal-hold confirmation, receipts, pointer CAS, and atomic deletion; `src/cadrumo/application/user_profile/`.
- [x] `W01.P02.S06` - Have Sol Medium jointly review KDF calibration and supervision, envelope and artifact AAD, capsule publication, journal recovery, and application-owned local deletion safety; `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/`.

## Wave `W02` - profile lifecycle and sessions

Move profile discovery, activation, session state, and handover onto the custody substrate; the transport wave consumes the resulting canonical capsule.

### Phase `W02.P03` - discovery and lifecycle ownership

Make committed UUID capsules the sole source for discovery, profile projection, and local lifecycle transitions.

- [x] `W02.P03.S07` - Have Terra XHigh make the profile repository and aggregate project only committed UUID capsules through sole lifecycle writers; `src/cadrumo/application/user_profile/`.
- [x] `W02.P03.S08` - Have Terra XHigh consolidate committed-marker discovery and the existence-only retired-path detector/refusal without legacy reads or keyring probes; `src/cadrumo/application/workflow/_profile_bucket_scan.py`.
- [x] `W02.P03.S09` - Have Sol Medium review lifecycle discovery, projection provenance, selection, and local-delete authority before login integration; `src/cadrumo/application/user_profile/`.

### Phase `W02.P04` - login and session handover

Authenticate a candidate profile without disturbing the active one, then publish a bounded session only after success.

- [x] `W02.P04.S10` - Have Terra XHigh authenticate profile B in a transaction-owned candidate namespace, clean it before swap on failure, and leave active A byte-for-byte intact; `src/cadrumo/application/user_profile/_login_session.py`.
- [x] `W02.P04.S11` - Have Terra XHigh replace active and persisted sessions with bounded DEK sessions, atomic reference swap, B promotion, best-effort keyring, and ordered retirement; `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/application/user_profile/_login_session.py`.
- [ ] `W02.P04.S12` - Have Sol Medium review candidate namespace cleanup, atomic in-process handover, B session promotion, keyring failure, post-swap recovery, and A non-resurrection; `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W02.P04.S27` - Have Sol Medium close the third profile-fact write door, which adopts facts from an external censal artefact with no schema judgement, and correct the write-door docstring that asserts a single-door invariant the tree does not hold; `src/cadrumo/application/user_profile/_cotejo_apply.py and src/cadrumo/application/wizard/_persistence.py`.
- [ ] `W02.P04.S26` - Have Terra XHigh restore wipeable key material across the current custody surface so recovery and password unwrap return zeroise-reachable buffers, noting the primitive is reachable today only through the forwarding port and must land after the surviving session package is renamed; `src/cadrumo/adapters/persistence/storage/custody/`.
- [x] `W02.P04.S43` - Have Terra XHigh re-root the hard-cutover absence gate across the whole application layer, teach it to read dynamic and attribute-string import targets and to flag a private-submodule reach, anchor its scope proof to the layer directory independently of the scan root, and declare each remaining live reach so the entry expires when its replacement lands; `src/cadrumo/application/tests/`.

## Wave `W03` - restorative transport and operator surfaces

Rebuild restore and operator access around current capsules and explicit secret channels; removal depends on every consumer being moved.

### Phase `W03.P05` - archive and restore

Separate safe deterministic transport from custody-authorized password restore and explicit recovery restore.

- [x] `W03.P05.S13` - Have Terra XHigh rebuild deterministic sealed archive transport framing without recovery.wrap, shared-master assumptions, or retired format parsing; `src/cadrumo/adapters/persistence/storage/bucket/`.
- [ ] `W03.P05.S14` - Have Terra XHigh implement password-only restore, explicit restore-recover lineage, exclusive recovery-artifact export-import, and new-identity portability; `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`.
- [ ] `W03.P05.S15` - Have Sol Medium review archive roots, hostile transport refusal, artifact export-import warnings and proof, restore publication, and rollback limits; `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/`.

### Phase `W03.P06` - CLI and TUI authority

Expose canonical profile verbs and secret channels through typed action envelopes and truthful operator surfaces.

- [ ] `W03.P06.S16` - Have Terra XHigh expose canonical profile restore, restore-recover, and delete verbs through action envelopes and one-shot secrets-fd; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W03.P06.S17` - Have Terra XHigh update root bootstrap, TUI login, locales, and status projection to remove old environment and provider channels; `src/cadrumo/entrypoints/`.
- [ ] `W03.P06.S18` - Have Sol Medium review CLI and TUI secret handling, typed outcomes, bootstrap exemptions, and local-only operator guarantees; `src/cadrumo/entrypoints/cli/`.
- [ ] `W03.P06.S42` - Have Terra XHigh close the drift between the curated operator help and the registered command tree, which advertises a first-run profile creation verb that no longer resolves, leaving command-line profile creation reachable only through the terminal interface, and gate the two surfaces against each other so a verb can never again be advertised without being registered; `src/cadrumo/entrypoints/cli/`.

## Wave `W04` - retire superseded custody

Remove every shared-master, provider-routing, recovery-mirror, and legacy-format surface after its consumers have moved; final proof depends on absence.

### Phase `W04.P07` - hard removal and negative audit

Remove shared-master custody and prove no retired path remains reachable or recognized.

- [ ] `W04.P07.S19` - Have Terra XHigh dissolve the forwarding port package in five ordered parts. Turn its string indirections into plain imports, no cycle existing to break. Delete the hand-copied module-shaped protocols that photocopy an adapter facade surface and serve no narrowing purpose, and the casts they existed to type. RELOCATE the record-shaped protocols that genuinely narrow a collaborator, one symbol per atomic commit with its full consumer sweep, testing each in turn. A concept the domain owns and adapters must satisfy goes beside the existing label-authority protocol in the domain. Otherwise a narrow view needed by one composing consumer goes into that consumer's own package beside its lifecycle actions, where an application ports module already exists and already holds the envelope, sentinel and recovery-envelope ports. Never leave a standalone package holding protocols for consumers that live elsewhere. The borrowed private aliases then dissolve because borrower and borrowed become one module. Then replace every remaining direct provider consumer with canonical per-profile custody and session material across storage, the tax-authority adapters, the application owners and command-line composition; `src/cadrumo/application/profile_custody/ and src/cadrumo/application/user_profile/_custody_ports.py and src/cadrumo/domain/user_profile/_protocols.py and src/cadrumo/adapters/persistence/storage/ and src/cadrumo/adapters/outbound/aeat/ and src/cadrumo/application/ and src/cadrumo/entrypoints/cli/`.
- [ ] `W04.P07.S20` - Have Terra XHigh delete retired provider, global recovery, raw-Argon, bootstrap, payload, locale, and legacy test surfaces after the replacement sweep; `src/cadrumo/adapters/persistence/storage/master_key/; src/cadrumo/adapters/persistence/storage/{__init__.py,_rotation.py,_kdf_bounds.py,errors.py}; src/cadrumo/application/{bucket_maintenance/,user_profile/}; src/cadrumo/entrypoints/cli/{__init__.py,_bootstrap_exempt.py,_config/,_config_payloads.py,tests/}; src/cadrumo/{core/_storage_taxonomy_locations.py,tests/master_key.py}`.
- [ ] `W04.P07.S21` - Have Sol Medium perform a negative architecture audit proving only an existence-only retired-path detector remains and no legacy custody route is reachable; `src/cadrumo/`.
- [ ] `W04.P07.S28` - Have Terra XHigh relocate the surviving per-profile session, wipe and identity residue into the custody package that the accepted decision names as sole authority, in one atomic move, so no surviving primitive is left behind a shared-master name; `src/cadrumo/adapters/persistence/storage/master_key/ and src/cadrumo/adapters/persistence/storage/custody/`.
- [ ] `W04.P07.S29` - Have Terra XHigh extend the existence-only retired-path detector to recognise retired keystore members alongside the plaintext manifest, so a retired shared-master store is detected and routed to re-enrolment rather than read; `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`.
- [ ] `W04.P07.S30` - Have Terra XHigh collapse the forwarding profile-custody port into one canonical route to the session and custody surface, making that route exclusive so no application module reaches the adapter package by a second path, and removing the mirror protocols and delegate wrappers that duplicate names already owned elsewhere; `src/cadrumo/application/profile_custody/ and src/cadrumo/application/`.
- [ ] `W04.P07.S31` - Have Terra XHigh fold the three unconstrained kibibyte Argon2 parameter models onto the ADR-canonical mebibyte custody record and dissolve the shared-bounds module whose only purpose was holding an import cycle open between two of them; `src/cadrumo/adapters/persistence/storage/`.
- [ ] `W04.P07.S32` - Have Sol Medium triage the fifteen auth test modules deleted under the discovery step against the twenty-two production auth modules still live, then restore the coverage that still applies or consciously retire each module with its reason recorded; `src/cadrumo/application/auth/tests/`.
- [ ] `W04.P07.S33` - Have Terra XHigh re-establish the strict roundtrip and anti-tautology proof for the profile-record persistence boundary that the discovery step deleted, populating every defaultable field with a non-default value and proving load refuses a mutated on-disk payload; `src/cadrumo/application/user_profile/tests/`.
- [ ] `W04.P07.S34` - Have Terra XHigh give bucket rename, bucket delete, retention-floor enforcement and archive inspect a successor owner after their removal from the maintenance service, or record each as deliberately retired with the operator route that replaces it; `src/cadrumo/application/bucket_maintenance/`.
- [ ] `W04.P07.S35` - Have Terra XHigh harden the import-hygiene shim detector so a forwarding layer written as wrapper definitions is caught, not only one written as import aliases, since the wrapper form evades the zero-real-definitions test by construction; `dev/quality/import_hygiene_scan.py`.
- [ ] `W04.P07.S36` - Have Sol Medium first rule whether per-profile recovery will adopt the mnemonic at all, since the codec and its canonical wordlist currently have no consumer anywhere, then either split them out as their own home or delete both halves with the wordlist and its wheel pin, rather than preserving a survivor with nobody to serve; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W04.P07.S37` - Have Terra XHigh stop the custody key-derivation calibration from measuring its cost grid on hosts that enrol a profile per test, adopting the fixed point the function already returns when measurement cannot complete, so enrolment stops costing ten supervised child processes without weakening any wrap; `src/cadrumo/core/config.py and src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py`.
- [ ] `W04.P07.S38` - Have Terra XHigh make the core hashing module the true single owner of canonical-record encoding it already claims to be, emitting utf-8 unescaped and refusing non-finite numbers, and repoint all eight implementations onto it with roundtrip and anti-tautology coverage for the changed persisted digest; `src/cadrumo/core/hashing.py and src/cadrumo/adapters/persistence/storage/ and src/cadrumo/application/`.
- [x] `W04.P07.S39` - Have Terra XHigh delete the re-export bridge module in the custody package and repoint its sole consumer at the two modules it forwards to, in one commit; `src/cadrumo/adapters/persistence/storage/custody/_label_head.py`.
- [ ] `W04.P07.S40` - Have Sol Medium confirm or refute that the modelo export stages fichero bytes through a predictable unhardened temporary name at an operator-chosen destination, and if confirmed bring that staging under the hardened write contract that governs sensitive financial data; `src/cadrumo/application/modelo/_export.py`.
- [ ] `W04.P07.S41` - Have Terra XHigh restore or remove the duplicate-label refusal that two live modules import from the profile facade but which is defined nowhere in the tree, an unrecorded casualty of the capsule discovery step that raises on import today; `src/cadrumo/application/user_profile/ and src/cadrumo/application/wizard/_commands.py`.
- [ ] `W04.P07.S44` - Have Sol Medium rule whether the operator-scope refusal introduced alongside the capsule cutover is intended, since it replaced a session fallback with a raise that two unguarded callers now hit where they previously succeeded, then pin that refusal with coverage, which it has never had on any of its twenty references; `src/cadrumo/application/auth/_operator_scope.py`.
- [ ] `W04.P07.S45` - Have Terra XHigh make the module coverage gate judge a property rather than static reachability, since one import from any surviving test currently keeps every module in a package reported as covered, which is how fifteen deleted test modules left twenty-two live modules unproven without the gate noticing; `src/cadrumo/tests/test_every_module_has_test_coverage.py`.

## Wave `W05` - end-to-end proof

Prove the hard cutover with real local filesystem, subprocess, CLI, TUI, and read-only DEHu flows; this is the final safety and architecture gate.

### Phase `W05.P08` - real-system verification

Exercise the actual local system and read-only DEHu path, then complete an independent security architecture proof.

- [ ] `W05.P08.S22` - Have Terra XHigh add real filesystem and subprocess custody matrices for isolation, calibration, supervision, crash recovery, deletion, and destructive reset; `src/cadrumo/adapters/persistence/storage/custody/tests/`.
- [ ] `W05.P08.S23` - Have Terra XHigh run and codify real CLI, TUI, recovery-isolation, artifact, and live read-only DEHu routes without remote writes; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W05.P08.S24` - Have Sol Medium complete the final security and architecture proof against every accepted custody invariant and execution record; `.vault/audit/`.
- [ ] `W05.P08.S25` - After S24 proves the hard cutover, perform the explicitly authorized local-only destructive reset of the existing disposable retired/shared-master store through the new canonical application-owned profile deletion authority, capture journal and receipt evidence, re-enrol only current-format profiles, never read/adopt/migrate retired custody, never delete through raw filesystem or SQL, and perform no AEAT or external mutation; `src/cadrumo/application/user_profile/; .vault/exec/`.
