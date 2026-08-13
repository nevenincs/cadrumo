---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:949494485930a0b5c122ec25580bc0f187c1ea27bb630dd40a84ed953dcb0c6c'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-password-custody` adr: `per-profile password custody authority` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Normal unlock is exactly: select an existing profile, enter its password, and unlock it. Runtime provider availability, a shared master key, or optional recovery material must not replace or obstruct that authority. The incident and option space are grounded in `2026-08-13-profile-password-custody-research`.

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

- A valid profile password must be necessary and sufficient for normal unlock.
- Profiles require independent compromise, loss, rotation, backup, and deletion boundaries.
- Recovery is optional and orthogonal; keyring storage is session acceleration only.
- On-disk mutation must remain deterministic after crashes, concurrent operations, and partial publication.
- Password envelopes permit offline guessing; online controls cannot claim otherwise.
- The current configured format is cut over destructively. No legacy reader, inference, adoption, or migration survives.

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

- **Runtime-selected shared master key:** rejected because provider drift can strand profiles and a profile password is not independently sufficient.
- **Shared root key wrapped by each profile password:** rejected because root loss and compromise retain a cross-profile blast radius.
- **Password-derived data encryption:** rejected because password and KDF rotation would require complete data re-encryption.
- **Random per-profile DEK wrapped by the profile password:** accepted because it matches the unlock contract and isolates profiles while allowing wrapper rotation.

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

- `ProfileCustodyEnvelope` version 1 is the only production custody format.
- DEK rotation is unsupported. A changed `dek_epoch` returns `DEK_ROTATION_UNSUPPORTED`.
- A coherent offline rollback of every capsule artifact cannot be detected without an external monotonic witness. The product must state this limit.
- Current Argon2 and authenticated-encryption dependencies are stable. Process supervision requires a canonical adapter over Windows Job Objects and POSIX process controls.
- Normal commands never read retired content. Old artifacts cause refusal and permit only explicit destructive reset or re-enrollment.

<!-- Technical limitations, e.g.: depends on non-mature library, frontier feature, requires rigorous research. 'Frontier' risk, e.g. technology is new and falls outside the implementing model's training cutoff.

List out the blocking constraints, and features, gaps needed for reliable implementation. Must explicitly evaluate how stable 'parent' features are if this adr
relies on another feature. -->

## Implementation

### Password envelope and DEK proof

Each immutable profile UUID owns one random 32-byte data-encryption key (DEK). `custody/envelope.v1.json` is the sole normal-unlock authority. It contains a strict schema, UUID, monotonically increasing password-envelope generation, immutable random 128-bit `dek_epoch`, password encoding identifier, bounded Argon2id record, authenticated DEK wrap, previous-envelope digest, and self-digest. The self-digest covers canonical JSON excluding only itself. Duplicate or unknown JSON members are refused.

Password-wrap authenticated additional data binds product, schema, profile UUID, generation, `dek_epoch`, key schedule, password encoding, KDF-record digest, and purpose. A committed encrypted sentinel under `data/` binds profile UUID, `dek_epoch`, data-format version, and sentinel purpose. Every password or recovery unwrap must authenticate this sentinel before accepting the DEK.

Passwords contain 15 to 256 Unicode scalar values and at most 1,024 strict UTF-8 bytes. Surrogates and invalid UTF-8 are refused. No normalization, trimming, folding, replacement, or composition rule applies. Spaces, paste, password managers, and scalar control values remain valid. Transports that cannot preserve the sequence refuse instead of rewriting it.

### Bounded KDF and worker supervision

Argon2id accepts only the versioned finite grid: memory `{19, 32, 64, 128, 256}` MiB, iterations `{2, 3, 4, 6, 8, 10}`, parallelism `{1, 2, 4}`, 16-byte salt, and 32-byte output. Validation precedes allocation. Enrollment calibration uses one discarded warm-up and five samples per eligible point, a two-second sample deadline, 15-second total deadline, the sample median, a 250 to 500 millisecond target, strongest-point ordering by memory, iterations, then parallelism, and fixed `64 MiB, t=3, p=1` fallback only when eligible. Unsupported local resources refuse; parameters never weaken.

Every Argon2 operation runs in a killable supervised child. The child performs Argon2 and password-wrap AEAD, then returns only a framed 32-byte DEK. The parent verifies the sentinel. The worker receives a minimal allowlisted environment, neutral working directory, and only bounded anonymous request and result pipes. No secret enters argv, environment, logs, or files.

Windows uses an assigned Job Object with kill-on-close, active-process, memory, and CPU limits. `STARTUPINFOEX` supplies an explicit handle list; every other handle is non-inheritable. POSIX uses a new process group, hard resource limits, close-from semantics, and exact `pass_fds`. The parent transmits no secret until the worker proves the limits in a ready handshake. Setup failure returns `KDF_SUPERVISION_UNAVAILABLE`; there is no in-process, thread, unsupervised, inherited-environment, or weaker fallback.

Per-profile online backoff and global/cross-process KDF concurrency protect resources only. Missing or corrupt throttle state means clear, never permanent denial. The product states that stolen envelopes support offline guessing.

### Optional recovery

`custody/recovery.v1.json` is a separate optional record with its own schema, generation, `dek_epoch`, KDF, AAD domain, digest chain, and wrapped copy of the same DEK. Password login must not stat, open, parse, digest, or validate this file. Missing, cancelled, inaccessible, malformed, or corrupt recovery cannot affect password login, activation, password rotation, normal backup, or normal restore.

Recovery enrollment occurs after activation. Rotation verifies the candidate before atomic replacement. Password rotation preserves valid recovery because the DEK and epoch do not change. Recovery removal requires current-password authentication. Recovery-based password reset increments the password-envelope generation and preserves the epoch.

A portable `profile-recovery-artifact/v1` contains UUID, `dek_epoch`, recovery generation and bounded KDF, recovery wrap, AAD descriptor, and canonical self-digest. It contains no mnemonic, password envelope, data, session, or keyring state. Export requires current-password authentication and exclusive creation. Import requires explicit naming, UUID/epoch agreement, mnemonic unwrap, and sentinel proof; it never overwrites enrolled recovery implicitly. Warnings identify offline-guessing exposure, separate-storage requirements, retained exported copies, and the fact that loss does not harm password login.

### Transactions and immutable capsule publication

Each capsule has `custody/`, `data/`, and immutable `profile.commit.v1.json`. The marker contains only marker schema, layout version, UUID, transaction UUID, publication kind, publication time, and canonical self-digest. It contains no envelope, epoch, sentinel, or inventory binding. Creation and restore build and fsync the marker inside a complete sibling staging capsule. One atomic directory rename publishes the capsule. Discovery recognizes only final UUID directories with a valid marker.

Login performs mandatory custody-transaction preflight before reading the password envelope. One bounded canonical journal records transaction UUID, operation, profile UUID, expected old generation/digest, proposed generation/digest, staged relative path, finite state, and self-digest. Preflight rolls back unverified intent, publishes verified compare-and-swap state, recognizes already-published bytes, repairs non-authoritative projections, revokes stale sessions, and refuses every unexplained combination. It never reads recovery material.

Root creation and selection journals capture exact old pointer existence, bytes, and digest plus intended replacement. Pointer publication is exact compare-and-swap and occurs last. Recovery never overwrites an independently changed pointer. Final capsules without a marker remain undiscoverable and are reconciled only by their matching root transaction.

### Sessions and profile handover

The keyring may store only a random session key under service `cadrumo:profile-session:v1` and account profile UUID. It wraps an already password-unlocked DEK for a default 15-minute idle and four-hour absolute lifetime. Session AAD binds profile UUID, custody generation/digest, authentication time, deadlines, schema, and purpose. Custody generation changes revoke sessions.

Profile B authenticates into transaction-owned candidate memory and staged session state while profile A remains unchanged. Failure before the active-reference swap destroys B's candidate state and leaves A byte-for-byte and semantically intact. Success atomically swaps the active reference, promotes B's staged session, attempts optional keyring acceleration, cleans candidate artifacts, and only then retires A. Keyring failure leaves a valid process B session.

Headless secrets use only bounded one-shot `--secrets-fd`; argv and environment secrets are forbidden. The canonical CLI verbs are `aeat config profile restore`, `aeat config profile restore-recover`, and `aeat config profile delete`. Action-envelope grammar belongs to the CLI successor ADR.

### Backup, restore, and rollback

The restorative archive's mandatory content root includes the archive header, immutable profile UUID, commit marker, password envelope, complete committed data, and canonical durable inventory. It excludes recovery, sessions, keyring entries, throttles, locks, journals, stages, pointers, caches, and sibling profiles. The profile password restores it on a fresh host without keyring access.

Normal restore is password-only and never discovers or falls back to recovery. `restore-recover` is a distinct explicit grammar requiring a named archive, named recovery artifact, mnemonic, and new password. It validates the original archive root first, verifies artifact, epoch, and sentinel, creates password-envelope generation `+1` with previous-digest lineage, records archive/artifact/new-envelope lineage and an immutable receipt, then publishes the verified capsule.

Generation, digest, journal, and compare-and-swap checks detect partial publication and mixed-file replay. They do not claim to detect a coherent offline rollback of the entire capsule and every witness.

### Hard cutover and deletion

Current-format recognition reads only the current commit marker. Detection of the closed retired path inventory is existence-only; it never parses retired content or probes the legacy keyring account. Any retired artifact returns `LEGACY_CUSTODY_DETECTED` and offers only explicit destructive reset or re-enrollment. No legacy reader, fallback, inference, migration, adoption, or dual format remains.

Profile deletion is journaled, crash-resumable, symlink/reparse-safe, and local-only by default. Legal and filing-hold preflight precedes confirmation bound to immutable UUID, inventory digest, and transaction UUID. Owner steps produce durable idempotent receipts. The operation revokes process secrets, deletes local session acceleration, compare-and-swap clears the pointer, atomically renames the capsule to a transaction-owned deleting path, and removes only local inventory without following links.

Deletion performs no AEAT or external write, token revocation, certificate revocation, cloud deletion, remote-registration deletion, or backup deletion. It reports retained remote state and external backup/recovery artifacts. External mutation requires a separate explicitly authorized operation, grammar, authentication, confirmation, journal, owner, and receipt.

<!-- A high-level overview (not a plan!) of HOW and WHAT will be implemented. Focus on condensed but clear prose that describes functionality layering.

Do not add code; code references must be persisted in a separate `{reference}` document. Important `{reference}` snippets must be summarized and referenced explicitly. -->

## Rationale

The selected model is the only option that makes the supplied profile password independently sufficient while containing compromise and rotation to one immutable profile UUID. Separate recovery, session, projection, transport, and external-operation owners prevent optional or unavailable mechanisms from becoming competing custody authorities. The transaction and capsule rules make every visible state attributable after a crash.

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

Every profile carries its own password envelope and DEK proof. Shared master-key and provider-fallback code must be removed rather than retained as compatibility. Recovery becomes optional without weakening disaster recovery. Backup is host-independent. KDF work gains an explicit denial-of-service and supervision boundary. The hard cutover requires destructive reset for current retired stores, DEK rotation remains unavailable, and coherent full-capsule rollback remains outside guarantees without an external witness.

<!-- Gains, but framed honestly. Difficulties. Pathways this feature opens. Pitfalls. -->
