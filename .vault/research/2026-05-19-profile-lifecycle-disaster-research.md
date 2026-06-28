---
tags:
  - '#research'
  - '#profile-lifecycle-disaster'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-operator-blind-dual-testimony-audit]]"
  - "[[2026-05-14-profile-bucket-lifecycle-adr]]"
---

# profile-lifecycle-disaster research: profile create / switch / read coherence (axis B)
Research axis B for the profile-lifecycle-disaster recovery campaign.
Investigates the create-switch-show/list disagreement surfaced by the operator
dual-persona testimony. Traces every write path from the CLI verb through to the
disk artifact and identifies the exact lines where the read contract fractures.

## What profile create writes today (verbatim call graph)
Entry point: src/aeat/entrypoints/cli/_config/__init__.py:518-524

The create verb is the wizard command built by
application/wizard/_commands.py:build_wizard_command(SETUP_FLOW).
The factory returns _command whose body runs at line 431.

Call graph in order:

1. _commands.py:471 -- workflow_state_repository() is called.
   Opens WorkflowStateRepository which constructs SecureObjectRepository().
   This requires an active bucket session. The engine URL resolves from
   Settings.aeat_database_url. With no pointer file no per-bucket URL exists,
   causing NoActiveBucketSessionError -- the bootstrapping deadlock.

2. _commands.py:472 -- repository.update(persist_answers) calls
   wizard/_persistence.py:persist_answers at line 71.

3. _persistence.py:90 -- read_profile_bucket(profile_name) consults
   <root>/buckets/<name>/manifest.toml to decide the branch.

4. _persistence.py:91 -- if pointer is None or resolve_active_bucket_id() != profile_name
   On a fresh install both are true so calls register_active_profile.

5. user_profile/_orchestration.py:register_active_profile (line 110):
   a. build_lifecycle_service(bucket_id=profile_id)
   b. service.register(RegisterProfileCommand(...)) at line 132
      Inside _lifecycle.py:ProfileLifecycleService.register (line 76):
      - _repository.exists(profile_id) read
      - _repository.save(record) write -- UserProfileRecord in SecureObjectRepository
      - emits PROFILE_BUCKET_CREATED + PROFILE_VALUES_UPDATED events
   c. state.model_copy(update=updated_at) -- in-memory only
   d. appends profile.created + profile.selected WorkflowEvents -- in-memory only
   e. _write_active_profile_pointer(profile_id) at line 147 -- writes <root>/active-profile

Missing from wizard create path:

- The bucket directory <root>/buckets/<name>/ is never created.
- manifest.toml is never written.
- provision_bucket_directory is never called.
- _provision_bucket_directory_idempotent from setup/_service.py is never invoked.

The manifest write lives only in setup/_service.py:initialize_workspace (line 108)
via _provision_bucket_directory_idempotent. The wizard create verb never calls
initialize_workspace.
## What profile switch writes today

Entry point: _config/__init__.py:260-281

1. repository.update(lambda current: select_profile(...))

2. user_profile/_orchestration.py:select_profile (line 151):
   a. build_lifecycle_service(bucket_id=profile_id)
   b. service.read(profile_id) at line 166 -- reads UserProfileRecord from
      SecureObjectRepository. Raises ProfileNotFoundError if the record is absent.
   c. _write_active_profile_pointer(profile_id) at line 171 -- rewrites pointer file.
   d. appends profile.selected WorkflowEvent in-memory.

3. resolve_active_bucket_id() reads pointer file back to confirm.
4. _emit_profile_activated_event(...) writes PROFILE_ACTIVATED to BucketEventHistoryRepository.

Switch succeeds because service.read finds the UserProfileRecord written by step 5b
of create. Switch re-writes the pointer file and returns exit 0. This explains the
testimony: switch exits 0 then show exits 2.

## What profile show and list read today

profile show (_config/__init__.py:341-394):

1. _profile_state().load() loads WorkflowState (requires session).
2. target = name or resolve_active_bucket_id() resolves name from pointer file.
3. pointer = read_profile_bucket(target) at line 361 calls
   _profile_bucket_scan.py:read_profile_bucket (line 28).
   Resolves <root>/buckets/<target>/manifest.toml.
   Returns None if the file does not exist.
4. if pointer is None: raises CliRefusedBoundaryError at line 363.

profile list (_config/__init__.py:236-257):

1. state = _profile_state().load()
2. record = state.active_profile_record() at line 243 calls
   _models.py:WorkflowState.active_profile_record (line 162).
   Resolves resolve_active_bucket_id() then reads SecureObjectRepository for the
   active bucket only.
3. Emits that one profile key-value table.

list does NOT call list_profile_buckets. It does NOT scan
<root>/buckets/*/manifest.toml. It shows only the active SecureObjectRepository
record -- which is why the testimony sees at most one profile with no active marker
and the second profile never appears.

## The disagreement, located

The wizard create path via wizard/_persistence.py never calls
_provision_bucket_directory_idempotent and therefore never writes manifest.toml.
The read-side verb show demands manifest.toml via read_profile_bucket at
_config/__init__.py:361-363. The contract fractures at:

- wizard/_persistence.py:91-96 -- calls register_active_profile which does not
  provision the bucket directory or write the manifest.
- _config/__init__.py:361-363 -- show refuses because read_profile_bucket returns
  None (manifest is absent).
- _config/__init__.py:243-244 -- list shows only the active SecureObjectRepository
  record not a manifest scan so a second profile is invisible regardless of manifest state.

The bootstrapping deadlock is a separate fracture: wizard/_commands.py:471 calls
workflow_state_repository() before the pointer file or bucket directory exists.
setup/_service.py:initialize_workspace avoids this by writing the pointer file at
line 118 before constructing workflow_state_repository() at line 120. The wizard
path does not do this.
## Comparable-CLI atomicity patterns

All six tools share one pattern: a single durable write to the same
storage medium as the read path with no separate registration step.

git init -- Creates the .git/ directory tree. Every git command that enumerates
the repository finds it immediately because the directory IS the index.

gcloud config configurations create NAME -- Writes
~/.config/gcloud/configurations/config_NAME using write-then-rename internally.
gcloud config configurations list scans that directory. Create and list share
the same filesystem path as their single source of truth.

kubectl create namespace NAME -- Sends one POST to the Kubernetes API server
which commits the namespace resource to etcd before responding.
kubectl get namespaces queries the same etcd key space.

bw create item (Bitwarden CLI) -- Sends one POST to the Bitwarden API.
Server-side state is immediately consistent; local vault cache bridges via
explicit bw sync (documented gap not a silent one).

gh repo create -- Sends one GraphQL mutation to GitHub API.
gh repo list queries the same API. Write-to-read immediately consistent.

docker volume create NAME -- Calls the Docker daemon synchronously.
The daemon writes volume metadata before responding. docker volume ls
queries the same database. Volume is enumerable as soon as create returns.

## Recommended atomic create contract

profile create NAME must be an all-or-nothing transaction. The profile is not
visible to list or show until the transaction completes.

Step a -- validate name. Call read_profile_bucket(name) first. If a manifest
exists refuse immediately with a clean CliRefusedBoundaryError. If the name
contains path separators refuse immediately. No disk mutation before this check.

Step b -- provision directory. Call provision_bucket_directory(root, name).
On failure return the error. No cleanup needed because no directory was created.

Step c -- write manifest (point of no return). Call write_manifest(paths, manifest)
via the write-then-rename pattern in _manifest_io.py:write_manifest. The os.replace
call makes the profile visible to read_profile_bucket and list_profile_buckets.
The profile does not exist until this rename completes.

Step d -- write pointer file. Call _write_active_profile_pointer(name) before
constructing any WorkflowStateRepository. This unblocks the engine URL resolution.

Step e -- write UserProfileRecord. Construct workflow_state_repository() and call
service.register(...) to persist the UserProfileRecord in the per-bucket
SecureObjectRepository.

On failure at step c or later: remove the manifest and bucket directory with
shutil.rmtree as a cleanup-only path.

The existing setup/_service.py:initialize_workspace already follows this order at
lines 108 -> 118 -> 120 -> 123. The fix is to route the wizard create verb through
initialize_workspace rather than calling wizard/_persistence.py:persist_answers
directly which bypasses the setup path.

## Duplicate-name handling

Today: wizard/_persistence.py:91 checks read_profile_bucket(profile_name).
Since the wizard path never writes the manifest a second profile create alice
finds pointer is None and calls register_active_profile again. This calls
_repository.exists(profile_id) at _lifecycle.py:79. If the SecureObjectRepository
record exists from the first call ProfileAlreadyExistsError is raised inside
repository.update at _commands.py:472 and propagates as an unhandled internal
error (exit 5 or 6) not a clean refusal.

What should happen: The manifest-scan check at step a is the authoritative duplicate
gate. If read_profile_bucket(name) returns non-None refuse immediately with a clean
CliRefusedBoundaryError. No directory provisioning no SecureObjectRepository write
no partial state is created on a duplicate-name attempt.

## Open questions for the ADR writer

1. Should profile list be changed to call list_profile_buckets() (manifest scan)
   and enumerate all profiles with an active marker or retain the current
   active-profile-facts display and add a separate sub-command for census?

2. Should list show names only and show show facts for a named profile or should
   list include facts for every profile?

3. The cold-start session requirement: should profile create bypass session
   construction entirely for the pre-first-profile state or should
   UnsecuredMasterKeyProvider auto-activate when
   AEAT_SECRET_STORE_BACKEND=unsecured and AEAT_ALLOW_UNENCRYPTED=1?

4. Is profile delete hanging (testimony Pain 4) in scope for the same ADR?
   Root cause is unconfirmed but likely a deadlock in
   BucketEventHistoryRepository.save() which also requires an active session.

5. Should the active-profile context cue (active profile: NAME (NIF) header
   on every command output) be a cross-cutting CLI root callback or per-verb?

## Constraints inherited by the ADR writer

From the 2026-05-18 cascade-closure ADR and project mandates:

- No shims, no aliases, no parallel chains, no deprecation paths. The wizard create
  verb must call a unified atomic create function not a shim wrapping both paths.
- No separate registration step outside the atomic create transaction. The manifest
  write IS the registration event; the profile does not exist before it.
- All-or-nothing: partial state (directory without manifest, pointer without directory)
  must not be observable by any read verb.
- profile list must be fixed to call list_profile_buckets() (manifest scan) and
  enumerate all profiles with an active marker.
- profile show already uses read_profile_bucket correctly and will work once create
  writes the manifest.
- profile switch already uses service.read correctly and will work once create
  writes the SecureObjectRepository record.
- No mocks fakes stubs in production or tests.
- Settings-not-naked-env: all config through pydantic-settings Settings.
- CLI root contract: exactly aeat config and aeat app. No third surface.
