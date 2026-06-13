---
tags:
  - '#adr'
  - '#profile-bucket-lifecycle'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-14-secure-backend-passkey-safety-research]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-04-12-data-storage-adr]]'
  - '[[2026-06-04-profile-bucket-lifecycle-research]]'
---

# `profile-bucket-lifecycle` adr: profile + bucket + vault lifecycle | (**status:** `accepted — execution-ready`)

## Problem Statement

The codebase ships a multi-profile surface (`aeat config profile use`,
`profile duplicate`, `profile remove`) on top of a single shared
cryptographic substrate. Research §5.1 documents the defect end-to-end:
every "profile" is a virtual partition keyed by a `bucket_id` column on
one shared `secure_objects` table, encrypted under one process-global
master key minted once at install (§5.1.6, §5.1.7). The active profile
has three competing definitions in flight at once -- the
workflow-state `active_profile` field, the Google adapter
`resolve_active_profile` override, and `Settings.aeat_default_profile_name`
which keys auth-acquisition lockfiles -- and they do not agree (§5.1.2).
Switching profile is a label change, not a vault switch: the master key
is not invalidated, the SQLAlchemy engine is not torn down, the outbound
storage adapter file handles are not closed, and no audit event records
the transition on the previous bucket (§5.1.3, §5.1.4). The
`--profile` override on the Google adapter is a partial-switch surface
that talks to the override bucket for Drive only while the rest of the
application continues to address the workflow-state-active bucket
(§5.1.2, §5.1.8).

The result is a defect-by-construction: a single exfiltration of `var/`
plus one passphrase yields plaintext for every profile on the install
(§5.1.6), and a single in-process bug can cross-leak rows across
buckets because the only barrier is uniform-`bucket_id`-filtering in
application code (§5.3). ADR-1 fixes the custody side; this ADR fixes
the lifecycle, layout, and switching side, and standardises the
terminology under which those concerns are named.

## Considerations

The research surveys twelve comparable tools (§5.2) and extracts six
invariants for safe multi-workspace systems (§5.2.1): each bucket has
its own key material; switching requires explicit teardown; the active
bucket is process-level state read at start; the bucket index is
listable without unlocking; locking is a first-class verb; concurrent
access is prevented or serialised. The Cryptomator
per-vault-directory model and the Borg / restic per-repository-keyfile
model both satisfy these invariants directly. 1Password's
unlock-the-account-and-every-vault-becomes-readable model does not
-- it converts multi-vault into multi-namespace-under-one-key, which is
exactly today's defect (§5.2, §5.3).

Three target architectures were surfaced in research §7: Option B.1
(single-bucket simplicity, no multi-bucket in v1), Option B.2
(multi-bucket directory model along Cryptomator / Borg lines), and
Option B.3 (B.2 plus an OS-keystore-stored bucket index against
tamper-the-index attacks). The threat-model expansion in §5.3
catalogues cross-bucket leak via shared caches, wrong-bucket writes
after a partial switch, default-profile silent fallback masking a
failed switch, backup tooling capturing every bucket under one
passphrase, tombstone records cross-leaking, and
`aeat_default_profile_name` desync.

Legal grounding (§4) confirms the autonomo retention duty under LGT
Art. 29 is per-declarant -- destroying a bucket without an
audit-export of what existed and when sacrifices retention compliance.

## Constraints

ADR-1 owns the cryptographic decisions: KDF choice, per-bucket vs
shared key schedule, recovery-mnemonic construction, OS-keystore
backend selection, recovery-wrap envelope format. This ADR consumes
those decisions and does not re-litigate them; it owns lifecycle,
on-disk layout, switching semantics, terminology, and concurrency.

The project mandate forbids backwards compatibility shims and partial
implementations: removed code stays removed, added code lands fully,
no migration tooling that re-encrypts the legacy interleaved `var/`
into per-bucket directories ships. The mandate also forbids transient
process metadata in source code, requires every record / manifest /
boundary-crossing structure to be a pydantic v2 model with strict
validation, and pins the CLI root to exactly two surfaces (`config`
and `app`) with no third surface ever.

The autonomo + business use case (one operator, two declarant
identities on one machine) is a hard product requirement; a
single-bucket-per-install architecture that pushes the second
identity into a separate `AEAT_HOME=...` shell does not satisfy it.

## Implementation

The choice is Option B.2 -- the multi-bucket directory model -- with
the precise contracts below. Option B.1 is rejected as a transitional
stepping stone (the project mandate forbids partial implementations);
the IMPLEMENTATION PLAN may sequence the rollout such that the
single-bucket case ships first and the second-bucket capability ships
shortly after, but that is a plan-phase concern. Option B.3 is
rejected for the first cut because the OS-keystore-stored bucket
index adds operational complexity (keystore-unavailable fallback in
headless / CI, cross-validation between filesystem scan and keystore
index) that the threat model does not yet justify; revisit if a
future threat-model update warrants it.

### 1. terminology mandate

`profile` is the user-facing identity (one NIF, one activity, one IVA
regime, language preferences). `bucket` is the encrypted on-disk
storage slice. The cardinality is **1:1**: every profile has exactly
one bucket and every bucket belongs to exactly one profile. `vault`
is permitted as a prose synonym for bucket in user-facing copy only;
it MUST NOT appear as a structural noun in code identifiers, CLI
verbs, manifest keys, or directory names. The Google Drive mirror
folder currently named `aeat-vault/` is renamed to `aeat-bucket/` to
resolve the collision flagged in research §5.0.

Concrete rename targets that the implementation must hit:

- `ProfileBucketPointer` (record at `src/aeat/application/workflow/_models.py`)
  is renamed `BucketPointer` and gains the manifest fields enumerated
  in subsection 3 below; the `profile_id` <-> `bucket_id` aliasing
  collapses to one identifier, `bucket_id`.
- `WorkflowState.active_profile` is renamed `active_bucket_id` and
  becomes a typed wrapper around the active-bucket pointer file
  introduced in subsection 5.
- `Settings.aeat_default_profile_name` is **removed**. No replacement.
- `aeat_default_profile_name` consumers in
  `src/aeat/application/auth/_acquisition_lock.py` and
  `src/aeat/application/auth/_sessions.py` re-key to the active
  bucket id from the pointer file.
- The Google adapter `--profile` override flag in
  `src/aeat/adapters/outbound/google/_profile_binding.py` is
  **removed**; profile selection happens only through the
  precedence chain defined in subsection 5.
- Locale catalogues (es / en / ca / hu) standardise on `bucket` for
  every storage-layer string and `profile` for every identity-layer
  string. Mixed `vault` strings that currently refer to encrypted
  storage slices are rewritten to `bucket`.
- Test fixtures, test names, error-message constants, and vault
  documents under `.vault/` referencing `profile_id` as a synonym
  for `bucket_id` are normalised to the one-identifier model.

### 2. on-disk layout

Every bucket lives at `<aeat-root>/buckets/<bucket-id>/` with three
subdirectories:

- `db/` -- the bucket's own SQLite database file, encrypted at the
  row-ciphertext layer per ADR-1's key schedule. One database per
  bucket; the legacy interleaved `var/aeat.db` is gone.
- `blobs/` -- the bucket's blob store (large ciphertext objects
  keyed by content hash).
- `audit/` -- the bucket's append-only audit log.

The keystore lives **outside** this tree. ADR-1 selects between OS
keychain (macOS Keychain, Windows DPAPI, Linux libsecret) and a file
backend at `<aeat-root>/keystore/<bucket-id>/`. Either way, ciphertext
and key material never share a parent directory; this enforces ADR-1's
key / ciphertext separation invariant and lets backup tooling exclude
the keystore path from off-site sync without dropping the ciphertext.
A second deliberate consequence: a stolen `<aeat-root>/buckets/` tree
without the keystore yields no plaintext for any bucket.

### 3. bucket manifest

Each bucket carries a plaintext manifest at
`<aeat-root>/buckets/<bucket-id>/manifest.toml` containing only
non-sensitive metadata. The manifest is a pydantic v2 model with
strict validation. Fields:

- `bucket_id` -- canonical identifier.
- `label` -- operator-chosen display name.
- `created_at`, `last_unlocked_at` -- UTC timestamps.
- `kdf_params` -- the Argon2id parameters chosen by ADR-1
  (`memory_cost`, `time_cost`, `parallelism`, `salt`, `version`).
  The salt IS public per Argon2 design; the manifest is the
  canonical home for it.
- `recovery_enrolled` -- boolean flag indicating whether a recovery
  wrap exists for this bucket. Wrapped key material itself NEVER
  lives in the manifest.
- `schema_version` -- integer supporting future format migrations
  without re-encrypting ciphertext.

The manifest NEVER contains the derived key, the wrapped key, the
passphrase, the recovery code, or any byte derivable from them.
Tampering with the manifest is detectable on next unlock because the
KDF params must match the wrapped-key envelope's recorded params, per
ADR-1.

### 4. discovery

`aeat config list-buckets` enumerates `<aeat-root>/buckets/` and
reads each `manifest.toml` without unlocking any bucket. Output
columns: `bucket_id`, `label`, `last_unlocked_at`, `recovery_enrolled`.
The verb refuses to ever touch ciphertext or the keystore -- it talks
to plaintext manifests only. This is the surface that lets the
operator decide which bucket to unlock without first proving they can
read another.

### 5. active-bucket selection (single source of truth)

The three competing definitions documented in research §5.1.2 collapse
to ONE: a plaintext pointer file at `<aeat-root>/active-bucket`
containing exactly the active `bucket_id`. Precedence (highest wins):

- An explicit `--bucket <id>` CLI flag (per-invocation, never
  persisted).
- The `AEAT_ACTIVE_BUCKET` environment variable (per-shell, useful
  for headless / CI invocations).
- The pointer file content (canonical default for interactive
  sessions; written only by `aeat config switch`).

If none of the above resolves, the process refuses to proceed with a
typed `NoActiveBucketError` whose message references
`aeat config list-buckets` and `aeat config switch`. `Settings.aeat_default_profile_name`
is removed -- it is not a fallback, not a default, not a
headless-only escape hatch. The Google adapter `--profile` override
is removed for the same reason: profile selection is a single
precedence chain that switches the entire process, not one adapter.

### 6. switching semantics

`aeat config switch <bucket-id>` performs the following sequence
exactly. Any step that fails aborts the switch and leaves the
process bound to the previous bucket:

- Lock the current bucket (run the `aeat config lock` semantics
  defined in ADR-1).
- Zeroise every in-memory key byte that referenced the previous
  bucket (the cache invalidation contract in subsection 7).
- Close every open SQLAlchemy engine, every open blob-store handle,
  every open audit-sink handle keyed to the previous bucket.
- Drop every `ClassVar` or module-global cache keyed to the
  previous bucket (subsection 7 enforces the absence of such
  state, but the switch path validates it).
- Atomically update the `<aeat-root>/active-bucket` pointer file
  via write-then-rename so a crashed switch never produces a
  truncated pointer.
- Stop. The new bucket is **not** auto-unlocked; the operator must
  invoke `aeat config unlock` explicitly on the new bucket.

No implicit unlock-on-switch. Silent partial switches are forbidden
by construction -- after the pointer update the new bucket has no
unlocked key material in memory at all, so no adapter can address
ciphertext under it until unlock runs.

### 7. cache invalidation

The class-level singletons identified in research §5.1.4 -- notably
`KeyringMasterKeyProvider._cache` at
`src/aeat/adapters/persistence/storage/master_key/_master_key.py:348-349`
and `FileFallbackMasterKeyProvider._cached_passphrase` /
`_cached_master_key` at `_master_key.py:473-475` -- are replaced with
per-process instance state owned by a `BucketSession` object
constructed at unlock and destroyed at lock. The `BucketSession`
holds the unlocked key material, the active SQLAlchemy engine, the
active storage-adapter providers, and any application-layer
memoisation keyed to the active bucket. Switching invalidates the
session by dropping the reference and zeroising the contained key
bytes.

The architectural invariant: **no module-global mutable state may
outlive a bucket switch**. Caches that legitimately need
process-lifetime scope (read-only registry data, decoded TOML
specifications, formula graphs) MUST NOT key on any bucket-scoped
value, and the switch path verifies the absence of such state via a
guard helper before flipping the pointer file. A test contract -- a
property-style test that switches between two buckets N times and
asserts that the master key bytes change on each switch -- prevents
the class-level cache defect from regressing.

### 8. per-bucket passphrase and per-bucket recovery code

Each bucket has its own KDF salt, its own Argon2id-derived KEK, its
own wrapped master key, and its own BIP-39 recovery mnemonic. Sharing
passphrases or recovery codes across buckets is **not supported** --
not as a UX convenience, not as an opt-in, not as a future capability.
The one-passphrase-breaks-all cross-bucket compromise model (research
§5.3) is closed by construction. ADR-1's recovery primitives extend
to the per-bucket schedule; the mnemonic that recovers bucket A MUST
NOT unwrap bucket B's key, even if both were enrolled in the same
session.

### 9. deletion

`aeat config delete-bucket <bucket-id>` requires a double confirmation:
a `--yes` flag AND a prompt at which the operator types the
`bucket-id` back verbatim. On success the verb:

- Atomically renames `<aeat-root>/buckets/<bucket-id>/` to a
  trash-prefixed sibling, then deletes the renamed tree. The
  rename-then-delete pattern survives crashes -- a half-deleted
  bucket is identifiable from its prefixed name on recovery.
- Removes the corresponding keystore entry (OS-keychain row or
  file under `<aeat-root>/keystore/<bucket-id>/`).
- Clears the `<aeat-root>/active-bucket` pointer file if its
  content matched the deleted bucket-id.

The verb is independent of `profile remove` (research §5.1.5
documents the current `profile remove` as a tombstone that retains
ciphertext rows). The tombstone-only verb is removed; deletion means
deletion.

### 10. export and import

`aeat config export-bucket <bucket-id> --out <path>` produces a sealed
archive containing the bucket's ciphertext tree, its `manifest.toml`,
and its recovery-wrapped key (the `master.recovery.key` envelope
emitted by ADR-1's recovery design). The archive does **not**
contain the passphrase, the OS-keystore entry, or the unwrapped
master key. Without the passphrase or the recovery code, the archive
is inert.

`aeat config import-bucket <archive>` registers the archive as a new
bucket under `<aeat-root>/buckets/<bucket-id>/`. The bucket appears
in `list-buckets` but cannot be addressed until `aeat config unlock`
succeeds against it (with passphrase or recovery code). Import does
not overwrite an existing bucket-id; a colliding import surfaces a
typed `BucketAlreadyPresentError` and exits.

### 11. concurrency

Each bucket carries a `<aeat-root>/buckets/<bucket-id>/.lock` file
acquired at unlock and released at lock (or at process exit via the
existing atexit hook). A second process attempting to unlock a
bucket whose lockfile is held fails fast with a typed
`BucketBusyError` whose message reports the holding PID. The operator
may opt into bounded waiting with `--wait <seconds>`. Different
buckets parallelise -- two processes against two different buckets
acquire two distinct lockfiles. Cross-process bucket switches against
the same bucket serialise through this lockfile.

The lockfile is independent of SQLite's own per-file locking; the
new per-bucket database layout (subsection 2) means SQLite's
file-level lock and the bucket-level lockfile align on the same
process-exclusive ownership window.

### 12. auth lockfiles and Google adapter bindings

The auth-acquisition lockfile namespacing in
`src/aeat/application/auth/_acquisition_lock.py` is re-keyed from
`Settings.aeat_default_profile_name` to the active bucket id read
from the precedence chain defined in subsection 5. The same change
lands in `src/aeat/application/auth/_sessions.py`. The
`_profile_binding.py:resolve_active_profile(profile_override)`
function in
`src/aeat/adapters/outbound/google/_profile_binding.py` loses its
`profile_override` parameter; its sole job becomes reading the
precedence chain. The `--profile` flag on every
`aeat config google ...` verb is removed.

The Google session-store records (OAuth client, OAuth token, Drive
folder ID) remain per-bucket-namespaced as today (research §5.1.8),
but they now live under the active bucket's own database file rather
than under one shared `var/aeat.db` filtered by `bucket_id` column.

### 13. no backwards compatibility

The legacy `var/` layout (one shared `aeat.db`, one shared
`secrets/master.key`, one shared `blobs/`, one shared `audit/`) is
not migrated. On first run the new code inspects `<aeat-root>/` for
the presence of `buckets/` and `active-bucket`; if either is missing,
the process refuses to operate and emits a typed
`LegacyLayoutDetectedError` whose message instructs the operator to
back up the legacy `var/` to cold storage and run `aeat config init`
to enrol a fresh bucket. No migration tooling ships. No
re-encryption pipeline ships. No `aeat config migrate-from-legacy`
verb is wired. The single autonomo dev environment scale of the
target audience makes a clean-cut wipe-and-re-enrol the honest
answer (research §6.8 reaches the same conclusion for ADR-1's
custody re-enrolment path).

## Rationale

Option B.2 satisfies every invariant the comparable-tools survey
extracted (research §5.2.1): each bucket has its own key material;
switching tears down before re-initialising; the active bucket is
process-level state read from a single source; the bucket index is
listable without unlocking; lock is a first-class verb; concurrent
access serialises through per-bucket lockfiles. It matches the
Cryptomator and Borg / restic reference designs that are already
shipped to millions of users with a defensible threat-model story.

Option B.1 (single-bucket simplicity) is rejected because the
autonomo + business use case is a hard product requirement and the
per-shell `AEAT_HOME=...` workaround places a substantial UX tax on
the most important multi-identity operator. The project mandate also
forbids partial implementations -- shipping single-bucket as a
"transitional" form of multi-bucket would leave a stub
`select_profile` / `profile duplicate` surface that violates the
no-stub rule.

Option B.3 (multi-bucket with OS-keystore index) is rejected for the
first cut because the threat model does not yet justify the
operational complexity. The tamper-the-index attack it defends
against (an adversary edits the plaintext index to point a bucket
label at someone else's wrapped key) is closed in B.2 by the unlock
contract: KDF params recorded in the manifest must match the
wrapped-key envelope, and any mismatch fails unlock. The index file
in B.2 is filesystem-scan-derivable, not authoritative; tampering
with a manifest mislabels a bucket in `list-buckets` output but
cannot redirect ciphertext to the wrong key. Revisit B.3 if a
future threat-model update materialises an adversary capable of
silent index-tampering.

The terminology mandate (subsection 1) resolves the three-way
naming drift documented in research §5.0 and §5.1.2.
`profile_id` <-> `bucket_id` aliasing has been the proximate cause of
the partial-switch defect and the cross-bucket leak risk; collapsing
the two into one identifier with `bucket` as the storage-layer noun
and `profile` as the identity-layer noun removes an entire class of
"which identifier is this argument bound to?" confusion in code
review.

## Consequences

### Code rewrites required

Files identified by research §5.1 that this ADR touches:

- `src/aeat/application/setup/_service.py` -- `initialize_workspace`
  stops passing one string as both `profile_id` and `bucket_id`;
  the bucket directory is provisioned under
  `<aeat-root>/buckets/<bucket-id>/` with subdirs `db/`, `blobs/`,
  `audit/`, and the `manifest.toml` is written.
- `src/aeat/application/user_profile/_orchestration.py` --
  `register_active_profile`, `select_profile`, and the tombstone
  path are rewritten against the new pointer-file precedence chain;
  `profile duplicate` is removed in favour of `export-bucket` +
  `import-bucket`.
- `src/aeat/application/wizard/_persistence.py` -- the wizard
  consumes the new `BucketPointer` record and emits a manifest.
- `src/aeat/application/workflow/_models.py` --
  `ProfileBucketPointer` -> `BucketPointer`; `WorkflowState.active_profile`
  -> `WorkflowState.active_bucket_id`.
- `src/aeat/adapters/persistence/storage/master_key/_master_key.py` --
  the `ClassVar` caches at lines 348-349 and 473-475 are replaced
  with `BucketSession`-scoped instance state.
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` --
  the `bucket_id` column filter pattern is removed; each bucket's
  database is its own file and rows belong to one bucket
  unconditionally.
- `src/aeat/adapters/persistence/storage/sql/_engine.py` -- the
  module-level engine singleton becomes a `BucketSession`-owned
  engine registry that constructs and tears down per unlock / lock.
- `src/aeat/adapters/outbound/storage/_factory.py` -- the
  `var/storage/<profile>/` directory composition becomes
  `<aeat-root>/buckets/<bucket-id>/blobs/`; the construction is
  scoped to the active bucket.
- `src/aeat/adapters/outbound/google/_profile_binding.py` -- the
  `--profile` override is removed; `resolve_active_profile`
  reads the precedence chain only.
- `src/aeat/application/auth/_acquisition_lock.py` and
  `src/aeat/application/auth/_sessions.py` -- the lockfile
  namespace re-keys to the active bucket id.
- The config-CLI surface (the `config` root referenced by the
  CLI-root mandate) gains `list-buckets`, `switch`,
  `delete-bucket`, `export-bucket`, `import-bucket`. The verbs
  `profile use`, `profile duplicate`, `profile remove` are
  removed.
- `Settings` (the application settings record) loses
  `aeat_default_profile_name` and the `aeat_local_storage_root /
  profile` composition; storage root resolution flows through the
  active-bucket pointer.

### User-visible behaviour change

- Existing installs refuse to operate against the legacy `var/`
  layout. The operator backs up `var/` and runs `aeat config init`
  to enrol a fresh bucket. No automatic migration.
- The CLI gains five new verbs under `aeat config`: `list-buckets`,
  `switch`, `delete-bucket`, `export-bucket`, `import-bucket`.
- The verbs `aeat config profile use`, `aeat config profile
  duplicate`, `aeat config profile remove`, and the `--profile`
  override on every `aeat config google ...` verb are gone.
- Switching no longer silently rebinds adapters under the previous
  master key; the operator now explicitly locks the previous bucket
  (implicit in `switch`) and unlocks the new one
  (`aeat config unlock`).

### Operational complexity

- Switching is no longer implicit. The operator runs `switch`,
  then `unlock`. The CLI surfaces a clear typed error if a verb is
  invoked between switch and unlock.
- Each bucket has its own passphrase and its own recovery code.
  The operator who runs two buckets manages two passphrases. The
  research-validated trade-off is that cross-bucket compromise no
  longer reduces to one-passphrase-breaks-all.

### Concurrency

- Second-process unlock attempts against a locked bucket fail fast
  with a typed `BucketBusyError` reporting the holding PID, instead
  of silently sharing state through a process-global cache.
- Parallel work against two different buckets is supported and
  serialises only at the per-bucket lockfile.

### Terminology rollout

- Code identifiers, CLI verbs, error-message constants, locale
  catalogues (es / en / ca / hu), test fixtures, and vault
  documents are normalised to the `bucket` / `profile` split.
- The Google Drive mirror folder is renamed from `aeat-vault/`
  to `aeat-bucket/` to resolve the structural-noun collision.
- The `vault` synonym survives only in prose, never in code or
  manifest schemas.

### Future considerations

- Option B.3 (OS-keystore-stored bucket index) remains a candidate
  if the threat model later warrants tamper-evident index storage.
- A future long-running daemon (anticipated for live notification
  capture work) will need a session-unlock protocol decision:
  strict-one-bucket-at-a-time, or N-buckets-unlocked-concurrently.
  This ADR adopts strict-one-bucket-at-a-time for the CLI surface
  by virtue of the single pointer file; the daemon question is
  deferred.
- The per-bucket database layout opens future per-bucket
  defence-in-depth options (per-bucket DEK derived from the
  per-bucket KEK, per-bucket schema version pinning) that are
  out of scope here but no longer architecturally blocked.
