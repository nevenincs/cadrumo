---
tags:
  - "#adr"
  - "#profile-password-custody"
date: '2026-08-13'
related:
  - '[[2026-08-13-profile-password-custody-research]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
  - '[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]'
  - '[[2026-08-13-cli-action-envelope-successor-adr]]'
supersedes:
  - '2026-05-14-secure-backend-passkey-custody-adr'
  - '2026-08-02-adjacent-domain-deduplication-store-scoped-login-throttle-adr'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4fadda95a257413968b5b19cab6627f4261e2b9fc7e026c0d29cc13fa18796ca'
---
# `profile-password-custody` adr: `per-profile password custody authority` | (**status:** `accepted`)

## Problem Statement

Normal unlock is exactly: select an existing profile, enter its password, and unlock it. Runtime provider availability, a shared master key, or recovery material must not replace or obstruct that authority. At the same time, publishing a profile without verified recovery permanently reduces its custody options because this architecture has no post-creation enrollment path. The incident and original option space are grounded in `2026-08-13-profile-password-custody-research`; the creation-lane contradiction and closure requirement are recorded by `2026-08-24-profile-password-custody-fresh-context-campaign-close-audit`, and the implemented verification boundary is reviewed by `2026-08-24-profile-password-custody-s206-recovery-parity-review-audit`.

## Considerations

- A valid profile password must be necessary and sufficient for normal unlock.
- Profiles require independent compromise, loss, rotation, backup, and deletion boundaries.
- Verified recovery is mandatory before profile publication but remains orthogonal to password authority.
- A valid profile password remains independently sufficient; unavailable, missing, or damaged recovery never obstructs login, password rotation, normal backup, or normal restore.
- Every creation caller, including direct application integrations, must participate in the bounded recovery handoff and exact verification protocol.
- Keyring storage is session acceleration only.
- On-disk mutation must remain deterministic after crashes, concurrent operations, and partial publication.
- Password envelopes permit offline guessing; online controls cannot claim otherwise.
- The current configured format is cut over destructively. No legacy reader, inference, adoption, or migration survives.

## Considered options

- **Runtime-selected shared master key:** rejected because provider drift can strand profiles and a profile password is not independently sufficient.
- **Shared root key wrapped by each profile password:** rejected because root loss and compromise retain a cross-profile blast radius.
- **Password-derived data encryption:** rejected because password and KDF rotation would require complete data re-encryption.
- **Random per-profile DEK wrapped by the profile password:** accepted because it matches the unlock contract and isolates profiles while allowing wrapper rotation.

## Constraints

- `ProfileCustodyEnvelope` version 1 is the only production custody format.
- DEK rotation is unsupported. A changed `dek_epoch` returns `DEK_ROTATION_UNSUPPORTED`.
- A coherent offline rollback of every capsule artifact cannot be detected without an external monotonic witness. The product must state this limit.
- Current Argon2 and authenticated-encryption dependencies are stable. Process supervision requires a canonical adapter over Windows Job Objects and POSIX process controls.
- Normal commands never read retired content. Old artifacts cause refusal and permit only explicit destructive reset or re-enrollment.
- Profile creation has no password-only outcome: registration requires an exact recovery handoff and verification exchange and refuses before publication when either cannot complete.
- Recovery enrollment exists only inside the profile-creation transaction. There is no post-creation enrollment writer, recovery-artifact import path, legacy adoption path, or fallback publication path.
- Recovery state is never a precondition for normal authentication or any password-authorized operation.

## Implementation

### Password envelope and DEK proof

Each immutable profile UUID owns one random 32-byte data-encryption key (DEK). `custody/envelope.v1.json` is the sole normal-unlock authority. It contains a strict schema, UUID, monotonically increasing password-envelope generation, immutable random 128-bit `dek_epoch`, password encoding identifier, bounded Argon2id record, authenticated DEK wrap, previous-envelope digest, and self-digest. The self-digest covers canonical JSON excluding only itself. Duplicate or unknown JSON members are refused.

Password-wrap authenticated additional data binds product, schema, profile UUID, generation, `dek_epoch`, key schedule, password encoding, KDF-record digest, and purpose. A committed encrypted sentinel under `data/` binds profile UUID, `dek_epoch`, data-format version, and sentinel purpose. Every password or recovery unwrap must authenticate this sentinel before accepting the DEK.

Passwords contain 8 to 256 Unicode scalar values and at most 1,024 strict UTF-8 bytes. Surrogates and invalid UTF-8 are refused. No normalization, trimming, folding, replacement, or composition rule applies. Spaces, paste, password managers, and scalar control values remain valid. Transports that cannot preserve the sequence refuse instead of rewriting it.

### Bounded KDF and worker supervision

Argon2id accepts only the versioned finite grid: memory `{19, 32, 64, 128, 256}` MiB, iterations `{2, 3, 4, 6, 8, 10}`, parallelism `{1, 2, 4}`, 16-byte salt, and 32-byte output. Validation precedes allocation. Enrollment calibration uses one discarded warm-up and five samples per eligible point, a two-second sample deadline, 15-second total deadline, the sample median, a 250 to 500 millisecond target, strongest-point ordering by memory, iterations, then parallelism, and fixed `64 MiB, t=3, p=1` fallback only when eligible. Unsupported local resources refuse; parameters never weaken.

Every Argon2 operation runs in a killable supervised child. The child performs Argon2 and password-wrap AEAD, then returns only a framed 32-byte DEK. The parent verifies the sentinel. The worker receives a minimal allowlisted environment, neutral working directory, and only bounded anonymous request and result pipes. No secret enters argv, environment, logs, or files.

Windows uses an assigned Job Object with kill-on-close, active-process, memory, and CPU limits. `STARTUPINFOEX` supplies an explicit handle list; every other handle is non-inheritable. POSIX uses a new process group, hard resource limits, close-from semantics, and exact `pass_fds`. The parent transmits no secret until the worker proves the limits in a ready handshake. Setup failure returns `KDF_SUPERVISION_UNAVAILABLE`; there is no in-process, thread, unsupervised, inherited-environment, or weaker fallback.

Per-profile online backoff and global/cross-process KDF concurrency protect resources only. Missing or corrupt throttle state means clear, never permanent denial. The product states that stolen envelopes support offline guessing.

### Mandatory creation-time recovery

`custody/recovery.v1.json` is a separate record with its own schema, generation, `dek_epoch`, KDF, AAD domain, digest chain, and wrapped copy of the same DEK. Every creation caller supplies a bounded recovery handoff and exact verification channel. The mnemonic is handed off before publication, and the caller must return an exact canonical proof. Cancellation, mismatch, malformed input, unavailable descriptors, transport failure, or shutdown aborts before capsule publication, active-pointer mutation, session publication, or any other durable profile state.

This requirement is enforced at the application registration boundary, not only by operator-facing CLI surfaces. Headless registration follows the `2026-08-23-cli-machine-secret-channel-unification-adr` inherited-handle and descriptor rules. Interactive registration uses masked exact re-entry. The mnemonic or verification secret never appears in argv, environment variables, stdout, stderr, action envelopes, logs, or result payloads.

Password login must not stat, open, parse, digest, or validate the recovery record. Missing, inaccessible, malformed, corrupt, or removed recovery cannot affect password login, activation, password rotation, normal backup, or normal restore. Recovery rotation applies only to already-enrolled recovery and verifies the candidate before atomic replacement. Recovery removal requires current-password authentication, is irreversible, and leaves no post-creation writer that can restore enrollment. Recovery-based password reset is a separate archive-and-lineage capability deferred by `2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr`; if a successor accepts it later, it must increment the password-envelope generation and preserve the epoch rather than fork the canonical rotation authority.

A portable `profile-recovery-artifact/v1` is a restore proof only. It contains UUID, `dek_epoch`, recovery generation and bounded KDF, recovery wrap, AAD descriptor, and canonical self-digest, but no mnemonic, password envelope, data, session, or keyring state. Export requires current-password authentication and exclusive creation. An artifact cannot import, replace, or create enrolled recovery. Explicit recovery restore requires a named capsule source, a named artifact, UUID and epoch agreement, mnemonic unwrap, and sentinel proof. Warnings identify offline-guessing exposure, separate-storage requirements, retained exported copies, and the fact that recovery loss does not harm password login.
### Transactions and immutable capsule publication

Each capsule has `custody/`, `data/`, and immutable `profile.commit.v1.json`. The marker contains only marker schema, layout version, UUID, transaction UUID, publication kind, publication time, and canonical self-digest. It contains no envelope, epoch, sentinel, or inventory binding. Creation and restore build and fsync the marker inside a complete sibling staging capsule. One atomic directory rename publishes the capsule. Discovery recognizes only final UUID directories with a valid marker.

Login performs mandatory custody-transaction preflight before reading the password envelope. One bounded canonical journal records transaction UUID, operation, profile UUID, expected old generation/digest, proposed generation/digest, staged relative path, finite state, and self-digest. Preflight rolls back unverified intent, publishes verified compare-and-swap state, recognizes already-published bytes, repairs non-authoritative projections, revokes stale sessions, and refuses every unexplained combination. It never reads recovery material.

Root creation and selection journals capture exact old pointer existence, bytes, and digest plus intended replacement. Pointer publication is exact compare-and-swap and occurs last. Recovery never overwrites an independently changed pointer. Final capsules without a marker remain undiscoverable and are reconciled only by their matching root transaction.

### Sessions and profile handover

The keyring may store only a random session key under service `cadrumo:profile-session:v1` and account profile UUID. It wraps an already password-unlocked DEK for a default 15-minute idle and four-hour absolute lifetime. Session AAD binds profile UUID, custody generation/digest, authentication time, deadlines, schema, and purpose. Custody generation changes revoke sessions.

Profile B authenticates into transaction-owned candidate memory and staged session state while profile A remains unchanged. Failure before the active-reference swap destroys B's candidate state and leaves A byte-for-byte and semantically intact. Success atomically swaps the active reference, promotes B's staged session, attempts optional keyring acceleration, cleans candidate artifacts, and only then retires A. Keyring failure leaves a valid process B session.

Headless scalar-secret transport defers to `2026-08-23-cli-machine-secret-channel-unification-adr`: every applicable CLI verb exposes the paired bounded `--secrets-stdin` and `--secrets-fd` channels, and argv and environment secrets remain forbidden. The canonical CLI verbs are `aeat config profile restore` and `aeat config profile delete`; `restore --artifact` selects the explicit recovery-artifact proof door within the single restore grammar. Action-envelope grammar belongs to the CLI successor ADR.

### Backup, restore, and rollback

The restorative archive's mandatory content root includes the archive header, immutable profile UUID, commit marker, password envelope, complete committed data, and canonical durable inventory. It excludes recovery, sessions, keyring entries, throttles, locks, journals, stages, pointers, caches, and sibling profiles. The profile password restores it on a fresh host without keyring access.

Normal restore is password-only and never discovers or falls back to recovery. `restore --artifact` is an explicit recovery proof within the same restore grammar, requiring a named capsule source (directory or sealed archive), named recovery artifact, and mnemonic. It validates the original capsule first, verifies artifact, epoch, and sentinel, and republishes the capsule under its existing password envelope unchanged. This door recovers the data path, not lost-password access; reset with a new password and new-envelope lineage remains deferred to the separate decision named above.

Generation, digest, journal, and compare-and-swap checks detect partial publication and mixed-file replay. They do not claim to detect a coherent offline rollback of the entire capsule and every witness.

### Hard cutover and deletion

Current-format recognition reads only the current commit marker. Detection of the closed retired path inventory is existence-only; it never parses retired content or probes the legacy keyring account. Any retired artifact returns `LEGACY_CUSTODY_DETECTED` and offers only explicit destructive reset or re-enrollment. No legacy reader, fallback, inference, migration, adoption, or dual format remains.

Profile deletion is journaled, crash-resumable, symlink/reparse-safe, and local-only by default. Legal and filing-hold preflight precedes confirmation bound to immutable UUID, inventory digest, and transaction UUID. Owner steps produce durable idempotent receipts. The operation revokes process secrets, deletes local session acceleration, compare-and-swap clears the pointer, atomically renames the capsule to a transaction-owned deleting path, and removes only local inventory without following links.

Deletion performs no AEAT or external write, token revocation, certificate revocation, cloud deletion, remote-registration deletion, or backup deletion. It reports retained remote state and external backup/recovery artifacts. External mutation requires a separate explicitly authorized operation, grammar, authentication, confirmation, journal, owner, and receipt.

## Rationale

The selected model is the only option that makes the supplied profile password independently sufficient while containing compromise and rotation to one immutable profile UUID. Mandatory verified recovery at the sole creation publication boundary prevents an irreversible password-only profile while keeping recovery separate from normal-login authority. Separate recovery, session, projection, transport, and external-operation owners prevent unavailable recovery or acceleration mechanisms from becoming competing custody authorities. The transaction and capsule rules make every visible state attributable after a crash.

## Consequences

Every profile carries its own password envelope and DEK proof and has verified recovery before publication. Shared master-key and provider-fallback code must be removed rather than retained as compatibility. Every creation caller must complete the bounded handoff and exact verification exchange; any failure leaves no published profile or durable profile state.

The profile password remains independently sufficient for normal operations. Recovery removal, loss, or damage reduces only disaster-recovery options and never blocks password login, password rotation, normal backup, or normal restore. Removal is irreversible because enrollment has no post-creation writer, and portable recovery artifacts remain explicit restore proofs rather than enrollment inputs.

Backup is host-independent. KDF work gains an explicit denial-of-service and supervision boundary. The hard cutover requires destructive reset for current retired stores, DEK rotation remains unavailable, and coherent full-capsule rollback remains outside guarantees without an external witness.
