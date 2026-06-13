---
tags:
  - '#research'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-axis-a-session-activation-research]]"
  - "[[2026-05-19-profile-lifecycle-disaster-axis-e-failure-mode-research]]"
---

# profile-lifecycle-disaster research: axis D - state-model coherence

Axis D maps every read and write site for the six concurrent sources of truth
encoding what profile is active and where its data lives. Research basis:
full grep sweep of src/aeat/ on branch chore/eliminate-shims on 2026-05-19.
Read-only inspection; no source modifications.

## State sources inventory (6)

### Source 1 - Settings.aeat_active_profile (env AEAT_ACTIVE_PROFILE)

Format: str | None injected from AEAT_ACTIVE_PROFILE into the pydantic
Settings singleton loaded via load_settings().

Readers:
- resolve_active_bucket_id() at _models.py:215 (canonical resolver,
  reads Source 1 first before falling through to Source 3).
- Settings._resolve_database_url_for_active_profile model validator at
  core/config.py:873 reads self.aeat_active_profile directly without
  going through resolve_active_bucket_id().

Writers: No runtime writer. Set only via shell env or
override_settings(aeat_active_profile=...) in tests.

Role: Highest-priority rung. For CI, headless invocations, and the CLI
--profile flag (which sets an override_settings block).

### Source 2 - Settings.aeat_database_url (computed from Sources 1+3)

Format: SQLAlchemy URL sqlite:///.../buckets/<bucket-id>/db/aeat.db.

Readers:
- create_engine_from_settings at sql/engine.py:118,150,176.
- core/i18n/_render.py:105 for cache keying.
- Tests that pass Settings(aeat_database_url=...) bypass the profile chain.

Writers: Sole writer is _resolve_database_url_for_active_profile model
validator at core/config.py:845-903. When empty reads Sources 1 then 3;
when non-empty (test supply) returns early without consulting the chain.

Role: Derived value. Exists for SQLAlchemy ergonomics. Conceptually
redundant; kept for test ergonomics.

### Source 3 - active-profile pointer file (root/active-profile TOML)

Format: Two-line TOML bucket_id / schema_version. Typed via BucketPointer
at application/workflow/_bucket_pointer.py. Written atomically via
write-then-os.replace at _bucket_pointer_io.py:48-61.

Readers:
- resolve_active_bucket_id() at _models.py:218 via read_pointer() (second rung).
- Settings._resolve_database_url_for_active_profile at config.py:882-892 reads
  the same TOML via tomllib.loads directly, NOT via read_pointer().

Writers:
- _write_active_profile_pointer(bucket_id) in _orchestration.py:74-90:
  called by register_active_profile (line 147) and select_profile (line 171).
- initialize_workspace() at setup/_service.py:118 before the repo.
- _clear_active_profile_pointer() at _orchestration.py:93-107: called by
  remove_active_profile and config_profile_delete.
- config_profile_logout at _config/__init__.py:762.
- config_profile_rename at _config/__init__.py:~591+ when renamed profile was active.

Role: Canonical on-disk default for interactive sessions.

### Source 4 - per-bucket manifest files (root/buckets/id/manifest.toml)

Format: TOML with bucket_id, label, created_at, last_unlocked_at, kdf_params,
recovery_enrolled, schema_version. Typed via BucketManifest at
storage/bucket/_manifest.py. Atomic write via _manifest_io.py.

Readers:
- read_profile_bucket(name) at _profile_bucket_scan.py:28-53 checks for
  root/buckets/name/manifest.toml. Returns ProfileBucketPointer(bucket_id=name)
  if present, else None. Used by: config_profile_show (line 361),
  config_profile_delete (416), config_profile_duplicate (456,459),
  config_profile_rename (572,575), config_profile_import (717,722),
  all four apoderado verbs (999,1038,1066,1087), _modelo.py:184,
  wizard/_persistence.py:90, google/_oauth_flow.py:75.
- list_profile_buckets() at _profile_bucket_scan.py:56-83 scans all
  manifests; replacement for retired WorkflowState.profiles.
- Four stale test sites (test_workflow_surface.py:184,
  test_ratios_verbs.py:150, test_profile_census_verbs.py:86,
  test_config_parity.py:82) call state.profiles[name]. The profiles
  attribute was retired from WorkflowState and will raise AttributeError.

Writers:
- write_manifest(paths, manifest) at _manifest_io.py:86-101 via
  _provision_bucket_directory_idempotent() in setup/_service.py:87.
  Called ONLY from initialize_workspace() at setup/_service.py:108.
- config_profile_rename reads and rewrites the manifest after directory rename.

Role: The gatekeeper for whether a profile exists from every CLI read path.

### Source 5 - WorkflowState encrypted state row

Format: Encrypted JSON envelope in the secure-object SQLite table.
WorkflowState no longer carries a profiles field (retired). Surviving fields:
auth, declarations, invoice_reviews, ledger_reviews, bucket_events, updated_at.

Readers: workflow_state_repository().load() as _profile_state().load().
Writers: workflow_state_repository().update(lambda s: ...) for all mutations.

Role: Auth state, filing draft pointers, bucket-event log. No longer carries
profile-discovery state. Stale comment in _orchestration.py:279 references a
state.active_profile field that does not exist on the current model.

### Source 6 - _active_session ContextVar[BucketSession]

Format: Python contextvars.ContextVar holding a BucketSession or None.
Defined at storage/master_key/_active_session.py:38.

Readers: get_active_master_key() at _active_session.py:76-98 called by every
encrypted column read/write. When None raises NoActiveBucketSessionError.

Writers: activate_session(session) at _active_session.py:54-73 (context
manager). Called from EphemeralMasterKeyProvider.__enter__ at
_master_key.py:828,901. No production CLI code path ever calls activate_session
or EphemeralMasterKeyProvider.__enter__ -- these are test fixtures only.
This is Defect A from the synthesis audit.

## Read-write disagreement zones

### Zone D1 - Manifest missing after register_active_profile (direct cause of F2)

The sharpest disagreement: directly causes create-succeeds / show-says-Unknown.

Write site: register_active_profile() at _orchestration.py:110-148.
Writes: Source 3 (pointer file) + encrypted DB record (via service.register).
Does NOT call provision_bucket_directory. Does NOT write manifest.toml.

Read site: config_profile_show at _config/__init__.py:358-368.
Calls read_profile_bucket(target) which gates on manifest.toml existence.
When absent returns None and raises CliRefusedBoundaryError(Unknown profile).

The wizard-driven profile create verb calls register_active_profile without
first calling initialize_workspace. Result: Source 3 written, encrypted DB
record written, Source 4 absent. Every CLI verb gating on Source 4 (show,
delete, duplicate, rename, all apoderado verbs) reports Unknown profile.

### Zone D2 - Stale state.profiles[name] in four tests

WorkflowState.profiles was retired. Four test files will raise AttributeError:
test_workflow_surface.py:184, test_ratios_verbs.py:150,
test_profile_census_verbs.py:86, test_config_parity.py:82.

### Zone D3 - Dual TOML parse paths with different validation depth

Write path: write_pointer() via BucketPointer pydantic model (strict).
Read path 1: read_pointer() via BucketPointer.from_toml() (strict; raises
ValidationError on malformed payload).
Read path 2: Settings._resolve_database_url_for_active_profile at
config.py:882-892 uses raw tomllib.loads + parsed.get with no pydantic
validation. A torn write valid as TOML but failing BucketPointer strict
validation would be silently accepted by path 2, rejected by path 1.

### Zone D4 - config_profile_import writes into active bucket; no manifest created

config_profile_import at _config/__init__.py:693-746 writes a UserProfileRecord
into the active bucket DB for target_id. No new bucket directory or manifest.toml
is created for target_id. Subsequent read_profile_bucket(target_id) returns None.
The imported profile is invisible to manifest-scan discovery.

### Zone D5 - select_profile validates via encrypted DB; show gates on manifest

select_profile() at _orchestration.py:151-172 calls service.read(profile_id)
(reads encrypted DB) then writes Source 3. Does NOT check Source 4.
config_profile_show checks Source 4 (manifest) before attempting the DB read.
A profile with a valid DB record but no manifest passes select_profile
(switch exits 0) but fails show (Unknown profile).

## Precedence chain verification

Canonical resolver: resolve_active_bucket_id() at _models.py:189-221.
Chain: Source 1 (env) first, Source 3 (pointer file) second, None if both absent.

Conforming call sites:
- WorkflowState.active_profile_bucket_id() at _models.py:183 - correct.
- WorkflowState.active_profile_record() at _models.py:171 - correct.
- read_active_profile() at _orchestration.py:247 - correct.
- _require_active() at _orchestration.py:283 - correct.
- require_active_bucket_id(), active_bucket_id_or_raise() at _models.py:224-263 - correct.
- CLI verbs calling resolve_active_bucket_id() directly - correct.

Non-conforming: Settings._resolve_database_url_for_active_profile at
config.py:873 reads self.aeat_active_profile directly and parses the TOML
inline rather than delegating to resolve_active_bucket_id(). Duplicates the
chain with looser validation; would silently diverge if a third rung were added.

Stale comment: _orchestration.py:279 documents a third rung state.active_profile
while the field migration is in flight. No such field exists on WorkflowState.
_require_active calls only resolve_active_bucket_id().

## Atomicity gaps

### Gap G1 - register_active_profile omits manifest write

register_active_profile at _orchestration.py:110-148 writes the encrypted DB
record and the pointer file. Missing: manifest.toml (Source 4). Every subsequent
CLI read gating on read_profile_bucket() reports Unknown profile.

### Gap G2 - initialize_workspace ordering dependency without transaction

Sequence at setup/_service.py:90-149:
1. _provision_bucket_directory_idempotent - Source 4 (manifest).
2. _write_active_profile_pointer - Source 3 (pointer).
3. Engine URL computed from Sources 1+3 (workflow_state_repository() call).
4. register_active_profile - encrypted DB record.

Crash between 1 and 2: manifest exists, no pointer.
Crash between 2 and 4: pointer + manifest, no DB record.
No filesystem transaction; no rollback on any step.

### Gap G3 - config_profile_rename is multi-step without rollback

Sequence at _config/__init__.py:559-636:
1. service.rename() - rewrites encrypted DB record under target id.
2. shutil.move(source_dir, target_dir) - renames bucket directory.
3. Read old + write new manifest (updating bucket_id and label).
4. _write_active_profile_pointer(target) if was active.

Between steps 2 and 3: manifest carries old bucket_id under new directory name.
Between steps 3 and 4: manifest says target, pointer says source.
No rollback mechanism for any step.

### Gap G4 - select_profile does not invalidate stale Source 2

select_profile writes Source 3. Source 2 (aeat_database_url) is computed at
Settings construction time. Safe because load_settings() constructs a new
Settings each call. Tests supplying aeat_database_url=... directly are isolated.

## Retirement candidates

### R1 - WorkflowState.profiles (retired at model; four tests stale)

Model retirement complete. Four test files still call state.profiles[name]
and will raise AttributeError. Update to use list_profile_buckets() /
read_profile_bucket(name).

### R2 - Stale state.active_profile comment in _orchestration.py:279

The comment references a field that does not exist. Remove it.

### R3 - Duplicate TOML parse in Settings._resolve_database_url_for_active_profile

Replace the inline tomllib.loads at config.py:882-892 with a call to
read_pointer(). Closes Zone D3, collapses Source 3 to one validated parse path.

### R4 - Settings model validator direct Source 1 read

Refactor _resolve_database_url_for_active_profile to call
resolve_active_bucket_id() rather than reading self.aeat_active_profile and
the TOML inline. R3 and R4 can be done together.

### R5 - EphemeralMasterKeyProvider / activate_session as test-only constructs

Promote to production path. Every CLI entry point that touches encrypted columns
must enter an activate_session block. ADR must assign ownership of this lifecycle.

## Comparable-CLI source-of-truth patterns

### gcloud (Google Cloud SDK)

Sources: global properties file, per-named config files under configurations/,
and active_config single-line pointer file. Existence of the config file is the
gating check. No encrypted state row, no in-memory ContextVar. 3 sources.

### kubectl (Kubernetes)

Sources: ~/.kube/config YAML with clusters, contexts, users stanzas, and
current-context key. Single file; active pointer is one key. 1 source.

### aws CLI (v2)

Sources: ~/.aws/credentials, ~/.aws/config, AWS_PROFILE env / --profile flag.
No pointer file; profile passed explicitly. No in-memory session ContextVar.
3 sources.

### bw (Bitwarden CLI)

Sources: encrypted vault cache file, BW_SESSION env var (base64 session key).
Session key is in-memory equivalent -- operator exports it explicitly.
No per-profile pointer file. 2 sources.

### Observations

All four tools keep which-profile-is-active in a single plaintext file or env
var, never in an encrypted row. Encrypted payload is profile data, not identity.
None use more than 3 sources. Only bw uses an in-memory session token and makes
it explicit via shell export. kubectl achieves the cleanest model: one file,
one key, zero redundancy.

## Recommended state model

Target: 3 sources, one resolver, one atomic write path.

Source A: AEAT_ACTIVE_PROFILE env var / --profile flag. Per-invocation override.
Consulted first by resolve_active_bucket_id().

Source B: root/active-profile TOML pointer file. On-disk default for interactive
sessions. Consulted second by resolve_active_bucket_id().

Source C: root/buckets/id/manifest.toml per-bucket manifests. Authoritative
existence registry. Every does-this-profile-exist check gates on this file.
Written atomically at profile creation.

Settings.aeat_database_url survives as a computed value derived from Sources A+B
via resolve_active_bucket_id(). Tests may still supply it directly.

_active_session ContextVar is a cryptographic gate, not a profile identity
source. Must be populated by the production CLI before any encrypted column op.

### Atomic write contract for create profile alice

1. Provision root/buckets/alice/ directory.
2. Write manifest.toml (Source C).
3. Write root/active-profile pointing at alice (Source B).
4. Open BucketSession (or EphemeralMasterKeyProvider in unsecured mode).
5. Write encrypted UserProfileRecord in the per-bucket DB.

### Atomic write contract for switch to alice

1. Verify manifest.toml exists for alice (Source C gate).
2. Overwrite root/active-profile pointer (Source B).
3. Open a BucketSession for alice.

### Precedence chain contract

Settings._resolve_database_url_for_active_profile MUST call
resolve_active_bucket_id() rather than re-implementing the chain.
resolve_active_bucket_id() is the single gated resolver for Sources A+B.

## Open questions for the ADR writer

1. Session ownership: CLI root callback vs. per-verb? Root is simpler but
   requires known active profile at startup; per-verb allows session-free verbs
   (--help, profile list, --version) to avoid session setup overhead.

2. Cold-start bootstrap: how does profile create open a session before any
   bucket exists? Options: EphemeralMasterKeyProvider as production fallback
   for unsecured mode; or create verb provisions bucket, sets pointer, then
   opens a fresh session for the DB write in one atomic sequence.

3. config_profile_import cardinality: currently writes into the active bucket.
   Under 1:1 profile:bucket, should import provision a new bucket for the
   imported profile?

4. WorkflowState bucket scoping: should WorkflowState carry an explicit
   bucket_id field, or remain implicitly scoped by its DB path?

5. Recovery path independence: config repair reset-state currently requires a
   session to read the table it means to clear (F4 from audit). Should the
   recovery path bypass the ContextVar with an explicit passphrase, or delete
   the encrypted row without reading it?

## Constraints inherited by the ADR writer

- No shims, compatibility layers, or parallel implementations.
- WorkflowState is frozen pydantic v2 with extra=forbid; adding fields is a
  migration event.
- Settings is pydantic-settings with env-var injection; aeat_database_url is
  referenced by many test fixtures supplying it directly -- the field must
  survive even if its computation path changes.
- AEAT_ACTIVE_PROFILE is a documented env var; removing it is a breaking change.
- The _active_session ContextVar contract (PEP 567 per-thread/task isolation)
  is correct; only call-site registration is missing.
- The activate_session context-manager API is correct; the ADR must decide
  where it is called, not whether it should exist.
