---
tags:
  - '#plan'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
tier: L2
related:
  - '[[2026-05-14-secure-backend-passkey-safety-research]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
---

# secure-backend-passkey-safety plan: passkey custody + bucket lifecycle execution

## Proposed Changes

This plan sequences the joint execution of two execution-ready ADRs against
the Secure backend: the master-passkey custody redesign (ADR-1, the
authorising decision behind every step that touches Argon2id, KEK / DEK
wrapping, BIP-39 recovery, lock / unlock, and the `aeat config` enrolment
verbs) and the profile + bucket + vault lifecycle redesign (ADR-2, the
authorising decision behind every step that touches the
`<aeat-root>/buckets/<bucket-id>/` directory model, the `BucketPointer`
pointer file, the active-bucket precedence chain, switching semantics,
cache invalidation, deletion, and export / import). One feature tag
`#secure-backend-passkey-safety` carries the plan; ADR-2's
`#profile-bucket-lifecycle` is acknowledged as a co-authorising decision
in this prose only and travels with the plan through the `related:`
frontmatter chain above.

The plan also discharges the three compounding defects catalogued in the
research: silent auto-mint at `src/aeat/application/setup/_service.py`
lines 12 - 57 [research 2.4]; co-location of wrapped key, KDF params,
salt, and ciphertext under one `var/` parent [research 2.2]; and the
dead-letter recovery surface pointing at `aeat security recover` /
`aeat security provision` strings inside
`src/aeat/adapters/persistence/storage/master_key/_master_key.py` at
lines 558 - 563, 619 - 622, 1056 - 1058 [research 2.5]. It removes the
process-lifetime `ClassVar` caches at the same module's lines 348 - 349
and 473 - 475 [research 2.6, ADR-1 5, ADR-2 7] and replaces them with a
per-bucket `BucketSession` instance.

The plan ships under the project mandates: no backwards compatibility
shims, no deprecation flags, no partial implementations, no transient
meta in source, pydantic v2 for every record / manifest / boundary
structure, src/aeat/ layout, and the CLI-root-two-only rule (canonical
verbs land under `aeat config`; no new `security` root). Per the legal
grounding mandate, every operator-facing copy string in the enrolment
and recovery flows preserves the verbatim Ley 58/2003 data-loss framing
from ADR-1 8.

The Phase sequencing builds bottom-up: pydantic models first (P01),
then filesystem layout and manifest IO (P02), then the cryptographic
core that consumes both (P03), then the active-bucket selection chain
that uses the pointer record (P04), then the CLI verb surface that
drives every subsystem (P05), then the enrolment wizard that wires
P03 + P04 + P05 into the operator's first run (P06), then the Drive
mirror rename (P07), then the codebase-wide terminology rollout (P08),
then the legacy-layout refusal-to-run gate (P09), then the end-to-end
integration suite (P10), then the user-facing documentation (P11).

## Steps

<!-- Each Step row is followed by a "Step detail" block that captures
     File targets, New surface, Existing code removed, Tests, and
     Acceptance per the authorising brief. The row grammar follows
     the plan-hardening CLI contract; the detail blocks supplement
     it with the per-step contract this plan mandates. -->

### Phase `P01` - foundation pydantic v2 record set

Lock down every record, manifest, and envelope as a pydantic v2 strict
model before any behavioural change so downstream phases consume
typed contracts only. No I/O, no crypto, no CLI; types and tests only.
[ADR-2 3, ADR-1 1, pydantic mandate]

- [ ] `P01.S01` - introduce `BucketManifest` pydantic model; `src/aeat/adapters/persistence/storage/bucket/_manifest.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_manifest.py`; new
`src/aeat/adapters/persistence/storage/bucket/__init__.py`. New surface:
`BucketManifest` pydantic v2 strict model carrying `bucket_id`, `label`,
`created_at`, `last_unlocked_at`, `kdf_params`, `recovery_enrolled`,
`schema_version` per ADR-2 3; `KdfParams` nested model. Existing code
removed: none in this step. Tests: `test_manifest.py` colocated under
`src/aeat/adapters/persistence/storage/bucket/` asserts strict-validation
rejects unknown keys, missing `bucket_id`, naive (non-UTC) datetimes,
non-positive `schema_version`, and that round-trip
`model_dump_json` / `model_validate_json` preserves byte equality of
the `salt` field. Acceptance: the model imports cleanly under
`uv run python -c "from aeat.adapters.persistence.storage.bucket import BucketManifest"`
and the colocated test passes; no consumer wired yet.

- [ ] `P01.S02` - introduce `KdfParams` Argon2id record; `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`. New
surface: `KdfParams` pydantic v2 strict model with fields `algorithm`
(literal `argon2id`), `version` (literal integer), `memory_cost`,
`time_cost`, `parallelism`, `salt` (16 bytes), `output_length`
(literal 32) per ADR-1 1 OWASP 2024 baseline. Validators reject any
parameter set outside the baseline window; the model exposes a
classmethod constructor `default()` returning the canonical 19 MiB / t=2
/ p=1 / 16-byte-salt / 32-byte-output instance. Existing code removed:
none in this step. Tests: `test_kdf_params.py` asserts the default
constructor materialises the OWASP-baseline numbers exactly (no
self-derivation; assertion is against the literal numeric constants
ADR-1 1 names; this is a constants-pin test, not a re-derivation),
asserts validation rejects `memory_cost=0`, `time_cost=0`, salt of
wrong length, unknown algorithm, and asserts JSON round-trip equality.
Acceptance: model importable; test passes.

- [ ] `P01.S03` - introduce `RecoveryRecord` BIP-39 envelope; `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_recovery_record.py`.
New surface: `RecoveryRecord` pydantic v2 strict model carrying
`wrapped_dek_b64`, `nonce_b64`, `tag_b64`, `mnemonic_word_count`
(literal 24), `hkdf_info`, `created_at` per ADR-1 4. Existing code
removed: none in this step. Tests: `test_recovery_record.py` asserts
validation rejects non-24 word counts, malformed base64, naive
datetimes, and asserts JSON round-trip equality. Acceptance: model
importable; test passes.

- [ ] `P01.S04` - introduce `BucketPointer` pointer-file record; `src/aeat/application/workflow/_bucket_pointer.py`.

Step detail. File targets: new module
`src/aeat/application/workflow/_bucket_pointer.py`. New surface:
`BucketPointer` pydantic v2 strict model carrying `bucket_id` and
`schema_version`. The record is the canonical typed wrapper around the
plaintext pointer file content described in ADR-2 5; the model owns
serialisation to and from the pointer file's chosen representation
(format adjudicated under Open questions). Existing code removed: none
in this step; the `ProfileBucketPointer` rename in
`src/aeat/application/workflow/_models.py` lands in P04. Tests:
`test_bucket_pointer.py` asserts strict validation rejects empty
`bucket_id`, asserts JSON round-trip. Acceptance: model importable;
test passes.

- [ ] `P01.S05` - introduce `ExportArchiveHeader` record; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_export_header.py`. New
surface: `ExportArchiveHeader` pydantic v2 strict model carrying
`bucket_id`, `manifest_digest`, `recovery_wrap_present` (boolean),
`archive_schema_version`, `created_at` per ADR-2 10. The header is the
plaintext frontmatter of every sealed export archive; the wrapped DEK
and recovery wrap travel as separate archive members. Existing code
removed: none in this step. Tests: `test_export_header.py` asserts
strict validation rejects unknown keys, missing digest, and asserts
JSON round-trip. Acceptance: model importable; test passes.

- [ ] `P01.S06` - introduce typed error hierarchy; `src/aeat/adapters/persistence/storage/bucket/_errors.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_errors.py`. New surface:
typed exception classes `NoActiveBucketError`, `BucketBusyError`,
`BucketAlreadyPresentError`, `LegacyLayoutDetectedError`, plus the
recovery and lock-state errors named in ADR-1 5 and ADR-2 5, 9, 11, 13.
Each exception carries a structured payload (active-bucket id where
relevant, holding PID for busy, conflicting bucket id for present).
Each is registered with the project error registry. Existing code
removed: none in this step; the dead-letter strings at
`_master_key.py:558-563, 619-622, 1056-1058` are rewritten in P05.
Tests: `test_bucket_errors.py` asserts each error's payload contract
and registry presence. Acceptance: errors importable; test passes.

Phase verification. Tests that must pass: every per-step test added
under P01. Invariants enforced: strict-validation rejects unknown
keys on every model (each model's own test enforces it). Manual
smoke: `uv run python -c "from aeat.adapters.persistence.storage.bucket import BucketManifest, ExportArchiveHeader"`
imports cleanly. Lint / type-check expectations: `uv run ruff check`
and `uv run mypy src/aeat/adapters/persistence/storage/bucket
src/aeat/adapters/persistence/storage/master_key/_kdf_params.py
src/aeat/adapters/persistence/storage/master_key/_recovery_record.py
src/aeat/application/workflow/_bucket_pointer.py`
return clean. Agent persona for every Step in P01:
`vaultspec-standard-executor`.

### Phase `P02` - filesystem layout and manifest IO

Materialise the `<aeat-root>/buckets/<bucket-id>/{db,blobs,audit}/`
directory model, the manifest read / write API, the keystore separation
contract, the pointer-file API, and the per-bucket `.lock` concurrency
primitive. No crypto, no CLI surface. [ADR-2 2, 3, 4, 5, 11]

- [ ] `P02.S01` - implement bucket directory provisioning; `src/aeat/adapters/persistence/storage/bucket/_layout.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_layout.py`. New surface:
`provision_bucket_directory(root, bucket_id)` creates
`<root>/buckets/<bucket-id>/` with the `db/`, `blobs/`, `audit/`
subdirectories per ADR-2 2; `bucket_paths(root, bucket_id)` returns a
typed `BucketPaths` pydantic record carrying each subpath. The
provisioning is atomic per directory (`os.makedirs(..., exist_ok=False)`
under a write-then-rename parent on first creation); a partial
filesystem state is detectable. Existing code removed: none in this
step; the legacy `var/storage/<profile>/` composition in
`src/aeat/adapters/outbound/storage/_factory.py` is removed in P08.
Tests: `test_layout.py` asserts the three subdirectories exist after
provisioning, asserts re-provisioning fails closed, asserts
`bucket_paths` returns a strict pydantic record. Acceptance: tests
pass against a tmp-path fixture.

- [ ] `P02.S02` - implement manifest read / write API; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`. New
surface: `write_manifest(paths, manifest)` and `read_manifest(paths)`
load and store the `BucketManifest` from P01.S01 at
`<bucket-dir>/manifest.toml` via atomic write-then-rename per ADR-2 3;
both functions are pydantic-strict at the boundary. The TOML
serialisation preserves the `salt` and `recovery_enrolled` fields
without lossy coercion. Existing code removed: none in this step.
Tests: `test_manifest_io.py` asserts write / read round-trip preserves
the manifest, asserts a partially-written manifest (crash injected via
a tmp-path stub on `os.replace`) is not surfaced as a torn read,
asserts a tampered manifest with an unknown key is rejected by strict
validation. Acceptance: tests pass.

- [ ] `P02.S03` - implement keystore separation contract; `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`. New
surface: `keystore_path(root, bucket_id)` returns the keystore root
outside `<root>/buckets/` per ADR-2 2 (concrete location adjudicated
under Open questions); a `validate_keystore_separation(root)` helper
fail-closes when the keystore path resolves under the buckets parent
or under the database directory. Existing code removed: none in this
step; the `aeat_secret_store_dir` settings consumer that allowed
co-location under `var/` is locked down via this helper. Tests:
`test_keystore_paths.py` asserts the helper raises on any nested-path
configuration. Acceptance: tests pass.

- [ ] `P02.S04` - implement pointer-file API; `src/aeat/application/workflow/_bucket_pointer_io.py`.

Step detail. File targets: new module
`src/aeat/application/workflow/_bucket_pointer_io.py`. New surface:
`read_pointer(root)` and `write_pointer(root, pointer)` operate on
`<root>/active-bucket` per ADR-2 5; the write path is
write-then-rename per ADR-2 6 so a crashed switch never produces a
truncated pointer; the read path returns `None` when the pointer file
is absent (the precedence chain in P04 handles the resolution).
Existing code removed: none in this step. Tests:
`test_bucket_pointer_io.py` asserts round-trip, asserts absent-pointer
returns `None`, asserts atomic rename leaves no partial file on a
simulated crash. Acceptance: tests pass.

- [ ] `P02.S05` - implement per-bucket `.lock` concurrency primitive; `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/bucket/_lockfile.py`. New
surface: `acquire_lock(paths, wait_seconds=0)` and `release_lock(paths)`
manage `<bucket-dir>/.lock` per ADR-2 11; the holder records its PID;
`BucketBusyError` (P01.S06) is raised when the lockfile is held by
another live process. The atexit hook releases the lockfile on
process exit. Existing code removed: none in this step. Tests:
`test_lockfile.py` asserts cross-process busy detection via a
subprocess fixture, asserts `--wait` semantics by polling, asserts
the atexit release runs on normal exit. Stale-lock detection on
abnormal exit is surfaced under Open questions. Acceptance: tests
pass.

Phase verification. Tests that must pass: every per-step test added
under P02. Invariants enforced: manifest read / write is byte-stable
under round-trip (`test_manifest_io.py`); keystore path can never
resolve under the buckets parent (`test_keystore_paths.py`); pointer
write is atomic (`test_bucket_pointer_io.py`); lockfile detects
cross-process contention (`test_lockfile.py`). Manual smoke: write a
manifest to a tmp path, read it back, assert equality at the
interactive shell. Lint / type-check expectations: `uv run ruff check`
and `uv run mypy` clean on every new module. Agent persona:
`vaultspec-standard-executor` for S01, S02, S04; `vaultspec-high-executor`
for S03 (keystore separation is a hard ADR-1 / ADR-2 invariant) and
S05 (concurrency is a hard ADR-2 invariant).

### Phase `P03` - cryptographic core (Argon2id, KEK derivation, DEK wrap, recovery wrap, zeroisation, idle-timeout state machine)

Replace the silent-mint, ClassVar-cached master-key resolver with a
`BucketSession`-scoped Argon2id KEK derivation and AES-256-GCM DEK
wrap pipeline. Wire the recovery primitives that already exist in
`src/aeat/adapters/persistence/storage/master_key/_recovery.py` (research
2.7) into the new core. Tests use known-answer vectors only; no
self-derivation. [ADR-1 1, 3, 4, 5, 6, ADR-2 7]

- [ ] `P03.S01` - implement `BucketSession` instance state; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
New surface: `BucketSession` class holding the unlocked KEK, the
unwrapped DEK, the active bucket id, the unlock timestamp, and the
idle-timeout configuration; `open(...)`, `close(...)` (zeroises),
`is_expired(now)`, `touch(...)`. The class is instance-scoped per
ADR-1 5 and ADR-2 7; no `ClassVar` caches. Existing code removed: in
this step, the `ClassVar` cache declarations at
`src/aeat/adapters/persistence/storage/master_key/_master_key.py` lines
348 - 349 (`KeyringMasterKeyProvider._cache`) and 473 - 475
(`FileFallbackMasterKeyProvider._cached_passphrase`,
`_cached_master_key`) are excised; their consumers route through
`BucketSession` instances acquired from a session registry owned by
the entrypoint layer. Tests: `test_bucket_session.py` asserts that
`close()` overwrites the key bytes (instance attribute is gone after
close), asserts `is_expired` correctly evaluates the idle window,
asserts that no module-global state survives a `close()` (a property
test attempts to read any module-level attribute that aliases the
key and fails). Acceptance: tests pass; `_master_key.py` no longer
declares any `ClassVar` caches.

- [ ] `P03.S02` - implement Argon2id KEK derivation; `src/aeat/adapters/persistence/storage/master_key/_kdf.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_kdf.py`. New
surface: `derive_kek(passphrase, kdf_params)` returns 32 bytes via
Argon2id at the OWASP 2024 baseline declared by `KdfParams.default()`
per ADR-1 1; the implementation consumes the existing `argon2-cffi`
dependency already in `pyproject.toml`. Existing code removed: the
inline `_derive_kek` and `_derive_kek_with_params` at
`_master_key.py` lines 203 - 218 and 771 - 781 are removed; their
sites route through the new module. Tests: `test_kdf.py` asserts the
derived KEK matches an `argon2-cffi` reference vector for a fixed
passphrase + salt + parameter tuple (known-answer; the expected bytes
come from the upstream library's own reference output captured once
under a documented invocation, not re-derived inside the test).
Acceptance: tests pass.

- [ ] `P03.S03` - implement AES-256-GCM DEK wrap and unwrap; `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`. New
surface: `wrap_dek(kek, dek)` and `unwrap_dek(kek, wrapped)` operate
under AES-256-GCM per ADR-1 3. The wrapped artefact carries `nonce`
(12 bytes), `ciphertext` (32 bytes), and `tag` (16 bytes); the typed
record `WrappedDek` is a pydantic v2 strict model declared in the
same module. Existing code removed: the wrap and unwrap inline logic
in the `FileFallbackMasterKeyProvider` at `_master_key.py` lines
504 - 506, 624 - 658 is removed; its sites route through the new
module. Tests: `test_dek_wrap.py` asserts round-trip identity for a
known DEK + KEK pair, asserts that a single-bit tamper of the tag
fails the AEAD verification, asserts wrong-KEK fails the AEAD
verification; the known-answer KEK + DEK + nonce + ciphertext + tag
vector is captured from a one-time golden run of the `cryptography`
library's own AESGCM primitive (upstream reference, not
self-derivation). Acceptance: tests pass.

- [ ] `P03.S04` - wire BIP-39 recovery wrap and unwrap; `src/aeat/adapters/persistence/storage/master_key/_recovery.py`.

Step detail. File targets: edit
`src/aeat/adapters/persistence/storage/master_key/_recovery.py`. New
surface: the existing `generate_recovery_key`, `wrap_master_key`,
`save_wrapped_master_key`, `encode_mnemonic`, `decode_mnemonic`, and
`unwrap_master_key` primitives are exposed through a typed facade
that consumes and returns the `RecoveryRecord` from P01.S03 and the
`BucketSession` from P03.S01 per ADR-1 4. Existing code removed: the
ad-hoc dict / bytes return shapes inside `_recovery.py` are replaced
with the typed record at the public boundary; the helpers themselves
keep their BIP-39 internals. The dead-letter `aeat security recover`
string at `_master_key.py:558-563` is removed in P05.S03. Tests:
`test_recovery.py` asserts that the existing BIP-39 reference vectors
(the BIP-39 spec's own test vectors for 24-word entropy-to-mnemonic
encoding) round-trip through `encode_mnemonic` / `decode_mnemonic` at
the typed boundary; asserts that a recovery-wrap round-trip returns
the original DEK bytes. Acceptance: tests pass.

- [ ] `P03.S05` - implement in-memory zeroisation contract; `src/aeat/adapters/persistence/storage/master_key/_zeroise.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_zeroise.py`. New
surface: `zeroise(buffer)` overwrites a mutable bytes-like buffer in
place; the function is consumed by `BucketSession.close()` per ADR-1 5.
Existing code removed: none in this step. Tests: `test_zeroise.py`
asserts the buffer contents change after `zeroise`; documents the
Python-runtime limit on guaranteed wipe (the test is a best-effort
contract test, not a guarantee that the GC has released every copy).
Acceptance: tests pass.

- [ ] `P03.S06` - implement idle-timeout state machine; `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py`.

Step detail. File targets: new module
`src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py`.
New surface: `evaluate_idle(session, now, configured_minutes)`
returns a typed `IdleEvaluation` record with fields `expired` and
`remaining_seconds`. The idle window defaults to 15 minutes per
ADR-1 5; the configured value lives in the bucket manifest. Every
CLI invocation runs the evaluator before granting access to the
session. Existing code removed: none in this step. Tests:
`test_idle_timeout.py` asserts that a session past its idle window
is reported `expired=True`; asserts that a fresh session is
`expired=False`; asserts that the `touch` path resets the counter.
Acceptance: tests pass.

- [ ] `P03.S07` - excise dead-letter error strings; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.

Step detail. File targets: edit
`src/aeat/adapters/persistence/storage/master_key/_master_key.py`. New
surface: every error message at lines 558 - 563, 619 - 622, and
1056 - 1058 that references `aeat security recover` or
`aeat security provision` is rewritten to point at the canonical
`aeat config <verb>` forms introduced in P05 per ADR-1 7. Existing
code removed: the three dead-letter string sites listed above are
replaced; the lazy-mint path at lines 432 - 453 (research 2.4) is
removed in P06.S01 because the wizard flow owns enrolment now.
Tests: `test_no_dead_letter_strings.py` greps the entire
`src/aeat/` tree for `aeat security recover` and
`aeat security provision` and asserts zero matches; the test guards
against regression. Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test added
under P03. Invariants enforced: no `ClassVar` cache survives on the
master-key module (`test_bucket_session.py` plus a static-AST
scanner test); no dead-letter `aeat security` string survives
(`test_no_dead_letter_strings.py`); AES-GCM round-trip and tamper
detection hold (`test_dek_wrap.py`); BIP-39 reference vectors hold
(`test_recovery.py`). Manual smoke: `uv run python -c` exercises a
`BucketSession.open` and `.close` cycle against a tmp manifest.
Lint / type-check expectations: clean on every modified module.
Agent persona: `vaultspec-high-executor` for every Step in P03
(crypto core, multi-file refactor, hard invariants).

### Phase `P04` - active-bucket selection (single source of truth)

Collapse the three competing active-bucket definitions (workflow
state, Google adapter override, `Settings.aeat_default_profile_name`)
into one precedence chain: `--bucket` flag > `AEAT_ACTIVE_BUCKET` env
> `<aeat-root>/active-bucket` pointer file. Rename
`ProfileBucketPointer` to `BucketPointer`. Remove the Google
`--profile` override surface. Re-key the auth-acquisition lockfile.
[ADR-2 1, 5, 12]

- [ ] `P04.S01` - implement the active-bucket resolver; `src/aeat/application/workflow/_active_bucket.py`.

Step detail. File targets: new module
`src/aeat/application/workflow/_active_bucket.py`. New surface:
`resolve_active_bucket(cli_flag, env, root)` consumes the precedence
chain per ADR-2 5; raises `NoActiveBucketError` (P01.S06) when none
resolves. Existing code removed: none in this step. Tests:
`test_active_bucket.py` asserts each precedence rung, asserts the
missing-everything case raises the typed error with a message
referencing `aeat config list-buckets` and `aeat config switch` per
ADR-2 5. Acceptance: tests pass.

- [ ] `P04.S02` - rename `ProfileBucketPointer` to `BucketPointer` and rename `WorkflowState.active_profile` to `active_bucket_id`; `src/aeat/application/workflow/_models.py`.

Step detail. File targets: edit
`src/aeat/application/workflow/_models.py`; ripple-edit every import
site. New surface: the renamed pydantic record per ADR-2 1; the
record consumes the file format from P01.S04. Existing code removed:
the `ProfileBucketPointer` and `WorkflowState.active_profile` names;
the `profile_id` <-> `bucket_id` aliasing collapses to one identifier
per ADR-2 1. Tests: `test_models.py` (existing) is updated to the new
names; `test_workflow_state_rename.py` asserts no `active_profile` /
`ProfileBucketPointer` symbol remains in `src/aeat/`. Acceptance:
tests pass; full `ruff check` is clean.

- [ ] `P04.S03` - remove `Settings.aeat_default_profile_name`; `src/aeat/core/config.py`.

Step detail. File targets: edit `src/aeat/core/config.py`. New
surface: none added in this step. Existing code removed: the
`aeat_default_profile_name` field and every consumer (verified by
grep). Per ADR-2 5 there is no replacement; the precedence chain
covers every prior use. Tests: `test_settings_no_default_profile.py`
asserts the field is absent and that an attempt to read it via
dynamic attribute access raises. Acceptance: tests pass.

- [ ] `P04.S04` - re-key the auth-acquisition lockfile; `src/aeat/application/auth/_acquisition_lock.py` and `src/aeat/application/auth/_sessions.py`.

Step detail. File targets: edit
`src/aeat/application/auth/_acquisition_lock.py`,
`src/aeat/application/auth/_sessions.py`. New surface: the lockfile
namespace consumes the active bucket id from `resolve_active_bucket`
per ADR-2 12. Existing code removed: every reference to
`aeat_default_profile_name`. Tests: `test_acquisition_lock.py`
(existing) is updated to the new lock-key derivation; the test
asserts the lockfile path is keyed to the active bucket id.
Acceptance: tests pass.

- [ ] `P04.S05` - remove the Google `--profile` override; `src/aeat/adapters/outbound/google/_profile_binding.py`.

Step detail. File targets: edit
`src/aeat/adapters/outbound/google/_profile_binding.py`. New surface:
`resolve_active_profile()` becomes a thin wrapper that reads the
precedence chain only per ADR-2 12; the `profile_override` parameter
is removed. Existing code removed: the `profile_override` parameter
and every caller passing it; the `--profile` flag on every
`aeat config google ...` verb is removed in P05.S04. Tests:
`test_profile_binding.py` (existing) is updated; a regression test
asserts the function rejects an unknown keyword argument.
Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test added
under P04. Invariants enforced: precedence chain order is exactly
flag > env > pointer (`test_active_bucket.py`); no
`ProfileBucketPointer` / `active_profile` / `aeat_default_profile_name`
symbol survives (rename tests + grep tests); auth lockfile is keyed
to the active bucket id (`test_acquisition_lock.py`). Manual smoke:
run `uv run aeat config --help` and confirm no `--profile` flag on
the Google subcommands. Lint / type-check expectations: clean.
Agent persona: `vaultspec-standard-executor` for S01, S04, S05;
`vaultspec-high-executor` for S02 and S03 (cross-cutting renames,
settings removal).

### Phase `P05` - CLI surface under `aeat config`

Wire the canonical verb set from ADR-1 7 and ADR-2 4, 6, 9, 10 into
`aeat config`: `init`, `unlock`, `lock`, `rekey`, `show-recovery`,
`verify-recovery`, `recover`, `list-buckets`, `switch`,
`delete-bucket`, `export-bucket`, `import-bucket`, plus the
`aeat config set idle-lock-minutes` key. Copy strings match the ADR
verbatim. The CLI root remains exactly two surfaces (`config` +
`app`); no `security` root. [ADR-1 7, 8, ADR-2 4, 5, 6, 9, 10]

- [ ] `P05.S01` - implement `aeat config init` skeleton; `src/aeat/entrypoints/cli/_config/_init.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_init.py`; edit
`src/aeat/entrypoints/cli/_config/__init__.py` to register the
command. New surface: the typer command signature gains
`--accept-data-loss-risk` and `--persist-recovery-wrap` per ADR-1 2,
4; the non-interactive gate refuses to mint unless
`AEAT_SECRET_PASSPHRASE` and `--accept-data-loss-risk` are both
present. The wizard flow lands in P06; this Step wires the command
shape only. Existing code removed: the silent-mint command body at
`src/aeat/entrypoints/cli/_config/__init__.py:628-695` is rewritten
in P06.S01. Tests: `test_init_command_shape.py` asserts the typer
signature carries the new flags and rejects the legacy `--profile`
option that previously aliased the bucket. Acceptance: tests pass.

- [ ] `P05.S02` - implement `aeat config unlock` and `aeat config lock`; `src/aeat/entrypoints/cli/_config/_unlock.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_unlock.py`. New surface: the
`unlock` verb prompts for the passphrase, derives the KEK via
P03.S02, unwraps the DEK via P03.S03, opens a `BucketSession`
(P03.S01); the `lock` verb closes the session, zeroises (P03.S05),
clears any keystore session-cache entry per ADR-1 5; both verbs
acquire / release the per-bucket lockfile (P02.S05). Existing code
removed: none in this step. Tests: `test_unlock_lock.py` asserts a
locked session refuses to read; asserts an unlock followed by a
lock is symmetric; asserts that a second-process unlock against a
locked bucket fails fast with `BucketBusyError`. Acceptance: tests
pass.

- [ ] `P05.S03` - implement `aeat config rekey`; `src/aeat/entrypoints/cli/_config/_rekey.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_rekey.py`. New surface: the
verb prompts for the current passphrase, unlocks, prompts for the
new passphrase with double-confirm, regenerates the KDF salt,
re-wraps the DEK under the new KEK, and writes the new wrapped DEK
plus fresh KDF params to the manifest atomically per ADR-1 6.
Existing code removed: none in this step (the `complete_recovery`
path at `_master_key.py:660-738` is wired in P05.S05). Tests:
`test_rekey.py` asserts that after rekey the old passphrase no
longer unlocks and the new passphrase does. Acceptance: tests pass.

- [ ] `P05.S04` - implement `aeat config show-recovery` and `aeat config verify-recovery`; `src/aeat/entrypoints/cli/_config/_recovery_view.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_recovery_view.py`. New surface:
`show-recovery` requires an unlocked session, then re-displays the
24-word recovery code per ADR-1 7; `verify-recovery` prompts the
operator to type all 24 words and confirms decoding matches the
wrapped recovery KEK. Existing code removed: none in this step.
Tests: `test_recovery_view.py` asserts the locked-session refusal,
asserts a mismatched verify path fails closed. Acceptance: tests
pass.

- [ ] `P05.S05` - implement `aeat config recover`; `src/aeat/entrypoints/cli/_config/_recover.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_recover.py`. New surface: the
verb accepts `--recovery-key <words>`, unwraps the DEK via the
recovery KEK using `_recovery.py`'s primitives (now typed through
P03.S04), prompts for a fresh passphrase with double-confirm,
re-wraps the DEK under the new passphrase-derived KEK, and writes
the new wrapped DEK plus a fresh KDF salt to the manifest atomically
per ADR-1 4. Existing code removed: the `complete_recovery` body at
`_master_key.py:660-738` is consumed through the new verb rather
than left dead. Tests: `test_recover.py` asserts that a fresh
recovery against a known-vector recovery code yields a session that
unlocks under the new passphrase. Acceptance: tests pass.

- [ ] `P05.S06` - implement `aeat config list-buckets`; `src/aeat/entrypoints/cli/_config/_list_buckets.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_list_buckets.py`. New surface:
enumerate `<aeat-root>/buckets/`, read each `manifest.toml` via
P02.S02, render the columns named in ADR-2 4. The verb refuses to
ever touch ciphertext or the keystore per ADR-2 4. Existing code
removed: the legacy `aeat config profile use` enumeration. Tests:
`test_list_buckets.py` asserts that buckets without an unlock
history still appear in the listing; asserts that the verb does
not invoke any master-key resolver. Acceptance: tests pass.

- [ ] `P05.S07` - implement `aeat config switch`; `src/aeat/entrypoints/cli/_config/_switch.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_switch.py`. New surface: the
verb runs the lock + zeroise + close-handles + atomic pointer
update sequence from ADR-2 6 in order; any step failure aborts and
leaves the process bound to the previous bucket. The new bucket is
not auto-unlocked per ADR-2 6. Existing code removed: the legacy
`aeat config profile use` and `profile duplicate` are removed;
`profile remove` is replaced by `delete-bucket` in P05.S08. Tests:
`test_switch.py` asserts the pointer-file update is atomic;
asserts no auto-unlock; asserts a switch-then-read fails closed
with a typed error pointing at `aeat config unlock`. Acceptance:
tests pass.

- [ ] `P05.S08` - implement `aeat config delete-bucket`; `src/aeat/entrypoints/cli/_config/_delete_bucket.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_delete_bucket.py`. New surface:
the verb requires `--yes` AND an interactive retype of the
`bucket-id` per ADR-2 9; on success it renames-then-deletes the
bucket tree, deletes the keystore entry, and clears the pointer
file if it matched. Existing code removed: the tombstone path in
`profile remove` is removed; deletion means deletion. Tests:
`test_delete_bucket.py` asserts the double-confirmation gate;
asserts a half-deleted bucket (rename-without-delete) is
identifiable; asserts the pointer file is cleared. Acceptance:
tests pass.

- [ ] `P05.S09` - implement `aeat config export-bucket` and `aeat config import-bucket`; `src/aeat/entrypoints/cli/_config/_export_import.py`.

Step detail. File targets: new module
`src/aeat/entrypoints/cli/_config/_export_import.py`. New surface:
`export-bucket` produces a sealed archive carrying the
`ExportArchiveHeader` (P01.S05), the ciphertext tree, the
manifest, and the recovery-wrapped key only per ADR-2 10; the
passphrase, the OS-keystore entry, and the unwrapped key are NEVER
included. `import-bucket` registers the archive as a new bucket
under `<aeat-root>/buckets/<bucket-id>/`; an import that collides
with an existing bucket id raises `BucketAlreadyPresentError`.
Existing code removed: none in this step. Tests:
`test_export_import.py` asserts the archive omits the passphrase
and unwrapped key; asserts import + unlock round-trip; asserts
the collision case raises. Acceptance: tests pass.

- [ ] `P05.S10` - implement `aeat config set idle-lock-minutes`; `src/aeat/entrypoints/cli/_config/_set.py`.

Step detail. File targets: edit
`src/aeat/entrypoints/cli/_config/_set.py` (new module). New
surface: the `set idle-lock-minutes <n>` verb writes the value to
the active bucket's manifest per ADR-1 5 with strict-positive
integer validation. Existing code removed: none in this step.
Tests: `test_set_idle_lock_minutes.py` asserts the value
round-trips through the manifest; asserts a non-positive value
fails closed. Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test
added under P05. Invariants enforced: no `aeat security` root is
present (`test_no_dead_letter_strings.py` from P03.S07 plus a
typer-AST scanner test asserting the CLI root contains exactly
`config` and `app`); switching never auto-unlocks
(`test_switch.py`); export never includes the passphrase or
unwrapped key (`test_export_import.py`); list-buckets never
touches ciphertext (`test_list_buckets.py`). Manual smoke: run
`uv run aeat config --help` and confirm every new verb is
present, no `security` root, no `--profile` flag. Lint /
type-check expectations: clean. Agent persona:
`vaultspec-standard-executor` for S01, S03, S04, S06, S10;
`vaultspec-high-executor` for S02, S05, S07, S08, S09 (each is a
load-bearing safety surface).

### Phase `P06` - enrolment wizard

Replace the silent-mint enrolment surface with the explicit
`aeat config init` flow: collect passphrase, double-confirm,
data-loss acknowledgement, recovery-code generation,
display-once, confirm-by-retype of N random positions, KEK
derivation, DEK sealing, manifest persistence, pointer-file set.
[ADR-1 2, 4, 7, 8]

- [ ] `P06.S01` - rewrite `aeat config init` body to drive the enrolment flow; `src/aeat/entrypoints/cli/_config/_init.py`.

Step detail. File targets: edit
`src/aeat/entrypoints/cli/_config/_init.py` (skeleton from
P05.S01); edit `src/aeat/application/setup/_service.py`. New
surface: the typer command body invokes the wizard prompter
(P06.S02) for passphrase double-confirm, data-loss-risk
acknowledgement, recovery-code display, and confirm-by-retype;
the setup service receives an already-open `BucketSession` from
the entrypoint layer per ADR-1 2 and refuses to proceed without
one. Existing code removed: the lazy auto-mint path at
`src/aeat/application/setup/_service.py:12-57` (research 2.4) is
removed; the `workflow_state_repository().update(...)` call no
longer triggers a silent encrypted write before the operator has
acknowledged the risk. The legacy command body at
`src/aeat/entrypoints/cli/_config/__init__.py:628-695` is removed.
Tests: `test_init_wizard.py` drives an end-to-end fake-tty
enrolment and asserts the manifest is written only after the
acknowledgement and the retype both succeed. Acceptance: tests
pass.

- [ ] `P06.S02` - extend the wizard catalogue and prompter for the new screens; `src/aeat/application/wizard/_catalogue.py` and `src/aeat/application/wizard/_prompter.py`.

Step detail. File targets: edit
`src/aeat/application/wizard/_catalogue.py`,
`src/aeat/application/wizard/_prompter.py`. New surface:
catalogue entries for passphrase double-confirm,
data-loss-risk acknowledgement, recovery-code display,
recovery-code confirm-by-retype (re-type N random positions; the
exact N is adjudicated under Open questions), and the
`--persist-recovery-wrap` opt-in screen per ADR-1 2, 4, 8; the
prompter gains a no-echo secret-input mode for passphrase entry
per ADR-1 2. Existing code removed: none in this step. Tests:
`test_wizard_enrolment_screens.py` asserts each new catalogue
entry renders the verbatim ADR-1 8 data-loss-framing sentence
(string-fixture test against the locale catalogues). Acceptance:
tests pass.

- [ ] `P06.S03` - add the verbatim ADR-1 8 data-loss sentence to es / en / ca locale catalogues; `locale/es/`, `locale/en/`, `locale/ca/`.

Step detail. File targets: edit each locale .po catalogue under
`locale/es/`, `locale/en/`, `locale/ca/`. New surface: the
verbatim Ley 58/2003 framing sentence from ADR-1 8 lands in each
locale; translation parity preserves the both / and structure
and the named surfaces (passphrase, recovery code, drafts,
evidence cache, transaction ledger). Existing code removed: none
in this step. Tests: `test_locale_data_loss_string.py` asserts
every enrolment, recovery, and lock-failure code path renders a
string containing the named surfaces. Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test
added under P06. Invariants enforced: the silent auto-mint path
is gone (`test_no_lazy_mint.py` asserts the setup service
refuses to proceed without an open session); every enrolment,
recovery, and lock-failure code path renders the verbatim ADR-1
8 sentence (`test_locale_data_loss_string.py`). Manual smoke:
run `uv run aeat config init` against an empty `<aeat-root>` and
walk through the wizard; assert recovery code is shown once and
the retype gate functions. Lint / type-check expectations: clean.
Agent persona: `vaultspec-high-executor` for S01 (load-bearing
flow); `vaultspec-standard-executor` for S02 and S03.

### Phase `P07` - Drive mirror rename

Rename the Google Drive mirror folder identifier from
`aeat-vault/` to `aeat-bucket/` to resolve the structural-noun
collision flagged in ADR-2 1. [ADR-2 1]

- [ ] `P07.S01` - rename the Drive mirror folder identifier; `src/aeat/adapters/outbound/google/_profile_binding.py` and the Drive folder discovery / creation sites.

Step detail. File targets: edit
`src/aeat/adapters/outbound/google/_profile_binding.py` and every
site under `src/aeat/adapters/outbound/google/` that names the
mirror folder. New surface: the canonical folder name is
`aeat-bucket/` per ADR-2 1. Existing code removed: the
`aeat-vault/` identifier and every fixture mention. Migration of
already-shared Drive folders is flagged under Open questions.
Tests: `test_records.py` (existing) and the no-legacy-modules
test are updated; `test_drive_mirror_name.py` asserts the
identifier is the new value. Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test
added under P07. Invariants enforced: no occurrence of
`aeat-vault` remains under `src/aeat/adapters/outbound/google/`
(grep test). Manual smoke: against a test Drive account, run the
Google bind flow and confirm the new folder name. Lint /
type-check expectations: clean. Agent persona:
`vaultspec-standard-executor`.

### Phase `P08` - terminology rollout

Normalise `vault`-as-storage-identifier to `bucket` across every
code identifier, error message, log string, and locale string in
`src/aeat/`. CLI help text may retain `vault` as a prose synonym
where natural per ADR-2 1. [ADR-2 1]

- [ ] `P08.S01` - normalise variable, class, function, and module names; `src/aeat/**`.

Step detail. File targets: every file under `src/aeat/` carrying
a `vault`-as-storage identifier. New surface: every code
identifier reads `bucket` (storage layer) or `profile`
(identity layer). Existing code removed: every code identifier
form `vault_*`, `*Vault*`, `*_vault_*` that names a storage
slice. Tests: `test_no_storage_vault_identifier.py` greps the
`src/aeat/` tree (excluding CLI help text strings) and asserts
zero matches against a curated identifier denylist.
Acceptance: tests pass.

- [ ] `P08.S02` - normalise error-message constants and log strings; `src/aeat/**`.

Step detail. File targets: every error message and log string
under `src/aeat/`. New surface: `bucket` for storage,
`profile` for identity per ADR-2 1. Existing code removed: every
operator-facing string that uses `vault` as a storage-layer
noun. Tests: `test_error_message_terminology.py` asserts no
error message in the typed error registry uses `vault` as a
storage-layer noun. Acceptance: tests pass.

- [ ] `P08.S03` - normalise es / en / ca / hu locale catalogues; `locale/**`.

Step detail. File targets: every .po catalogue under `locale/`.
New surface: every storage-layer string reads `bucket`; CLI help
text may keep `vault` as a prose synonym per ADR-2 1. Existing
code removed: every storage-layer `vault` string. Tests:
`test_locale_storage_terminology.py` asserts no locale entry uses
`vault` as a storage-layer structural noun. Acceptance: tests
pass.

- [ ] `P08.S04` - normalise outbound storage factory composition; `src/aeat/adapters/outbound/storage/_factory.py`.

Step detail. File targets: edit
`src/aeat/adapters/outbound/storage/_factory.py`. New surface:
the storage root composes as
`<aeat-root>/buckets/<bucket-id>/blobs/` per ADR-2 2. Existing
code removed: the `var/storage/<profile>/` composition.
Tests: `test_storage_factory.py` (existing) is updated; a new
assertion ensures the path resolves under the active bucket
directory. Acceptance: tests pass.

Phase verification. Tests that must pass: every per-step test
added under P08. Invariants enforced: no storage-layer
`vault` identifier survives in code, error messages, or locale
catalogues (the three terminology tests). Manual smoke: build
the CLI and grep `aeat --help` output; confirm `vault` only
appears as a prose synonym where natural. Lint / type-check
expectations: clean. Agent persona:
`vaultspec-low-executor` for S01, S02, S03 (mechanical
renames); `vaultspec-standard-executor` for S04 (path
composition change).

### Phase `P09` - refusal-to-run on legacy layout

Detect the legacy interleaved `var/` layout at first run and
refuse to operate with a typed error that instructs the operator
to back up `var/` to cold storage and run `aeat config init` from
scratch. No migration tool ships. [ADR-1 9, ADR-2 13]

- [ ] `P09.S01` - implement the legacy-layout refusal gate; `src/aeat/application/setup/_legacy_layout_gate.py`.

Step detail. File targets: new module
`src/aeat/application/setup/_legacy_layout_gate.py`; edit
`src/aeat/application/setup/_service.py` to invoke the gate at
process start. New surface:
`refuse_if_legacy_layout_detected(root)` raises
`LegacyLayoutDetectedError` (P01.S06) when
`<aeat-root>/buckets/` and `<aeat-root>/active-bucket` are both
absent AND a legacy `var/aeat.db` or `var/secrets/master.key` is
present per ADR-2 13. The error message instructs the operator
to back up `var/` to cold storage and re-enrol per ADR-1 9.
Existing code removed: any silent-tolerance of the legacy layout
inside the setup service. Tests:
`test_legacy_layout_gate.py` asserts the gate raises on a
synthesised legacy tree; asserts it permits a fresh tree.
Acceptance: tests pass.

Phase verification. Tests that must pass: `test_legacy_layout_gate.py`.
Invariants enforced: a legacy tree never produces ciphertext
reads under the new code. Manual smoke: against a fixture that
mirrors a pre-rollout `var/`, run `uv run aeat config init` and
confirm the refusal message. Lint / type-check expectations:
clean. Agent persona: `vaultspec-high-executor` (load-bearing
safety gate).

### Phase `P10` - integration and property tests

Exercise end-to-end flows: init - unlock - switch - unlock-new -
rekey - recover-from-mnemonic; concurrency lock conflicts; cache
invalidation under switch; auto-lock on idle; export / import
round-trip. [ADR-1 5, 6, ADR-2 6, 7, 10, 11]

- [ ] `P10.S01` - end-to-end init - unlock - switch - unlock-new flow; `src/aeat/entrypoints/cli/_config/test_e2e_switch.py`.

Step detail. File targets: new test module
`src/aeat/entrypoints/cli/_config/test_e2e_switch.py`. New
surface: a typer-runner test enrols two buckets in sequence,
switches between them, asserts the master key bytes differ on
each unlock (property test from ADR-2 7), asserts the previous
bucket's `BucketSession` is closed and zeroised before the
pointer flips per ADR-2 6. Existing code removed: none.
Acceptance: test passes.

- [ ] `P10.S02` - rekey and recover-from-mnemonic round-trip; `src/aeat/entrypoints/cli/_config/test_e2e_rekey_recover.py`.

Step detail. File targets: new test module
`src/aeat/entrypoints/cli/_config/test_e2e_rekey_recover.py`. New
surface: enrol a bucket, rekey under a new passphrase, then
recover via the 24-word mnemonic and verify the new bucket
unlocks under a third passphrase per ADR-1 4, 6. Acceptance:
test passes.

- [ ] `P10.S03` - concurrency lock-conflict test; `src/aeat/adapters/persistence/storage/bucket/test_e2e_concurrency.py`.

Step detail. File targets: new test module
`src/aeat/adapters/persistence/storage/bucket/test_e2e_concurrency.py`.
New surface: spawn two subprocesses against the same bucket,
assert the second sees `BucketBusyError` with the first's PID
per ADR-2 11. Acceptance: test passes.

- [ ] `P10.S04` - auto-lock-on-idle test; `src/aeat/adapters/persistence/storage/master_key/test_e2e_idle.py`.

Step detail. File targets: new test module
`src/aeat/adapters/persistence/storage/master_key/test_e2e_idle.py`.
New surface: set `idle-lock-minutes` to a small value, unlock,
advance the clock past the window, assert the next access
re-prompts per ADR-1 5. Acceptance: test passes.

- [ ] `P10.S05` - export / import round-trip test; `src/aeat/entrypoints/cli/_config/test_e2e_export_import.py`.

Step detail. File targets: new test module
`src/aeat/entrypoints/cli/_config/test_e2e_export_import.py`.
New surface: enrol a bucket, export, delete, import, unlock
under the original passphrase or the recovery code per ADR-2 10.
Acceptance: test passes.

- [ ] `P10.S06` - cross-bucket cache-invalidation property test; `src/aeat/adapters/persistence/storage/master_key/test_property_no_cross_bucket_state.py`.

Step detail. File targets: new test module
`src/aeat/adapters/persistence/storage/master_key/test_property_no_cross_bucket_state.py`.
New surface: hypothesis-driven property test that switches
between two buckets N times and asserts that the master key
bytes change on each switch AND that no module-level attribute
on `src/aeat/adapters/persistence/storage/master_key/` aliases
the prior key per ADR-2 7. Acceptance: test passes.

Phase verification. Tests that must pass: every per-step test
added under P10 plus the entire `uv run pytest` suite. Invariants
enforced: no cross-bucket key reuse, no auto-unlock on switch,
no concurrent unlock against one bucket, auto-lock on idle,
export inertness without passphrase / recovery, manifest
integrity end-to-end. Manual smoke: full `uv run aeat config`
walkthrough on a clean `<aeat-root>`. Lint / type-check
expectations: clean. Agent persona: `vaultspec-high-executor`
for every Step in P10.

### Phase `P11` - documentation

Land the user-facing CLI documentation, the lock / unlock /
recovery mental model, the README data-loss warning, and the
`reference/` vault document capturing the threat model and
invariants. [ADR-1 8, 10, ADR-2 1]

- [ ] `P11.S01` - write the user-facing CLI reference for `aeat config`; `docs/cli/config.md`.

Step detail. File targets: new file `docs/cli/config.md` (or the
project's canonical CLI-docs location, adjudicated by existing
docs layout). New surface: per-verb reference covering every
verb from P05; the verbatim ADR-1 8 data-loss sentence appears
in the `init` and `recover` sections. Existing code removed:
any stale `aeat security` reference in docs. Tests: a docs
smoke test asserts every verb from P05 is documented (lint
script counts headings against the typer registry). Acceptance:
docs build cleanly.

- [ ] `P11.S02` - write the lock / unlock / recovery mental-model doc; `docs/concepts/lock-unlock-recovery.md`.

Step detail. File targets: new file
`docs/concepts/lock-unlock-recovery.md`. New surface: the
operator-facing mental model for `BucketSession`, idle timeout,
recovery code custody, and the `verify-recovery` periodic test
per ADR-1 5. Acceptance: doc lints clean.

- [ ] `P11.S03` - update the README with the data-loss warning; `README.md`.

Step detail. File targets: edit `README.md`. New surface: a
top-section banner carrying the verbatim ADR-1 8 sentence and a
link to the mental-model doc. Acceptance: the README change
lands.

- [ ] `P11.S04` - capture the threat model and invariants in the vault `reference/` doc; `.vault/reference/2026-05-14-secure-backend-passkey-bucket-reference.md`.

Step detail. File targets: new vault doc
`.vault/reference/2026-05-14-secure-backend-passkey-bucket-reference.md`
authored via `vault add reference --feature
secure-backend-passkey-safety`. New surface: the post-execution
reference distillation per the vaultspec reference contract:
threat model from research 1, custody invariants from ADR-1, and
lifecycle invariants from ADR-2. Acceptance: `vault check` is
not run by this plan (per the brief), but the doc renders
clean.

Phase verification. Tests that must pass: docs lint and vault
add succeed. Invariants enforced: every verb from P05 appears in
the CLI reference; the verbatim ADR-1 8 sentence appears in the
README, the CLI reference, and the mental-model doc. Manual
smoke: open each new doc in the project's docs renderer.
Lint / type-check expectations: clean. Agent persona:
`vaultspec-low-executor` for S01, S02, S03 (mechanical authoring
against the ADRs); `vaultspec-standard-executor` for S04
(reference distillation).

## Parallelization

P01 has no dependencies; every Step in P01 can be authored in
parallel.

P02, P03, P04 depend on P01 (typed records). Within that, P02
(filesystem IO) and P03 (crypto core) are independent of each
other and may proceed in parallel; P04 (active-bucket resolver)
depends on P01.S04 (`BucketPointer` model) but is otherwise
independent of P02 and P03.

P05 (CLI verbs) depends on P02, P03, and P04. Within P05,
S02 - S05 (unlock, lock, rekey, recovery-view, recover) share a
session model and must serialise; S06 - S10 (list-buckets,
switch, delete-bucket, export-import, set) are independent of
each other and may proceed in parallel after S02 lands.

P06 (wizard) depends on P05.S01 + P03 + P04.

P07 (Drive mirror rename) is independent of P05, P06; can
proceed in parallel with P04 once P04.S05 lands.

P08 (terminology rollout) depends on the rename targets in P04
and P07 landing (so the storage-layer `bucket` names exist
upstream); P08 then sweeps the rest of the tree.

P09 (legacy-layout refusal) depends on P02 (it inspects the
layout) and P04 (it consults the pointer-file resolver).

P10 (integration suite) depends on P05, P06, P07, P08, P09.

P11 (documentation) depends on P05 (verb shape stable) and P06
(wizard flow stable); P11.S04 may land last alongside P10.

Hard ordering: P01 - P02 / P03 / P04 - P05 - P06 - P09 - P10 -
P11; P07 and P08 are interleaved between P04 and P10.

## Verification

The plan is complete when every Step in every Phase is closed.
The mission-success criteria distilled from ADR-1 and ADR-2:

- Every operator-facing enrolment, recovery, and lock-failure
  code path renders the verbatim ADR-1 8 Ley 58/2003 data-loss
  sentence; enforced by `test_locale_data_loss_string.py` and
  the docs smoke tests in P11.
- No `ClassVar` or module-global cache survives a bucket switch
  on the master-key module; enforced by
  `test_property_no_cross_bucket_state.py` (P10.S06).
- The active-bucket precedence chain is exactly flag > env >
  pointer; enforced by `test_active_bucket.py` (P04.S01).
- Switching tears down before re-initialising and never
  auto-unlocks; enforced by `test_switch.py` (P05.S07) and
  `test_e2e_switch.py` (P10.S01).
- Export archives are inert without passphrase or recovery
  code; enforced by `test_export_import.py` (P05.S09) and the
  e2e variant (P10.S05).
- A second-process unlock against a held bucket fails fast;
  enforced by `test_lockfile.py` (P02.S05) and the e2e variant
  (P10.S03).
- Idle-timeout auto-lock fires past the configured window;
  enforced by `test_idle_timeout.py` (P03.S06) and the e2e
  variant (P10.S04).
- No `aeat security` string survives anywhere in `src/aeat/`;
  enforced by `test_no_dead_letter_strings.py` (P03.S07).
- Legacy `var/` layouts refuse to run; enforced by
  `test_legacy_layout_gate.py` (P09.S01).
- Every record, manifest, and boundary structure introduced by
  the plan is a pydantic v2 strict model; enforced by the
  per-record validation tests in P01.

## Open questions

The following ambiguities are not adjudicated by ADR-1 or ADR-2
and surface here for follow-up before or during execution; none
of them should be answered by the plan author.

- Pointer-file representation. The plan models `BucketPointer`
  as pydantic and writes via P02.S04 with atomic rename, but
  the exact serialisation (single-line UTF-8 `bucket_id` plain
  text vs a one-line TOML document carrying `bucket_id =
  "..."`) is not specified by ADR-2 5. The plain-text form is
  the smallest possible artefact; the TOML form is consistent
  with `manifest.toml`. Choose explicitly before P02.S04
  executes.

- Cross-platform OS-keystore library choice. ADR-1 5 names the
  OS keystore session cache as the second mechanism by which a
  KEK survives across CLI invocations but does not fix the
  binding library. The repository already depends on `keyring`
  via the existing `KeyringMasterKeyProvider`; whether to keep
  that binding or migrate to a per-OS native binding
  (Keychain Services, DPAPI directly, libsecret) is open.

- Drive mirror migration. P07 renames the canonical folder
  identifier to `aeat-bucket/`. Operators with already-shared
  `aeat-vault/` folders on Drive face a manual rename. The
  plan declares no migration tool ships per the
  no-backwards-compat mandate; whether to surface a
  warning-only detector inside `aeat config google ...` is
  open.

- Exact `N` in "re-type N random recovery-word positions".
  ADR-1 4 names confirm-by-retype of "three random positions";
  the plan stages P06.S02 to accept an N that is fixed before
  the wizard catalogue lands. Confirm whether N = 3 (ADR-1 4)
  is the final value or whether the wizard catalogue
  parameterises it.

- Lockfile staleness detection on abnormal process exit.
  P02.S05 documents the atexit hook for normal exit; an
  abnormal exit (SIGKILL, OS crash, container OOM) leaves a
  stale lockfile carrying a dead PID. Whether the new unlock
  path probes `psutil`-style for the holding PID and reclaims
  a stale lock, vs surfaces a `--force` override on
  `aeat config unlock`, is open.

- Keystore concrete path layout. ADR-2 2 separates keystore
  from buckets; P02.S03 declares the helper and validates
  separation. The concrete default path (POSIX
  `~/.config/aeat/keystore/<bucket-id>/`, Windows
  `%LOCALAPPDATA%\aeat\keystore\<bucket-id>\`) parallels the
  ADR-1 4 recovery-wrap default but is not explicitly fixed
  for the keystore file backend. Confirm before P02.S03
  executes.
