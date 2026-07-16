---
tags:
  - '#reference'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-16'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-research]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
---

# `cli-authority-verb-conformance` reference: `Authentication logout and reset authority map`

This implementation Reference maps CLI verbs to backend authorities. It records
exact ownership, custody boundaries, duplicate status, and real-behavior
verification locations. It is not operator setup guidance or a contributor
procedure.

## Scope and lookup conventions

Use these locations according to the information needed:

| Need | Authoritative location |
|---|---|
| Operator authentication setup and use | `docs/how-to/authenticate-with-aeat.md` and generated command details in `docs/cli/config/auth.rst` |
| Contributor setup and support | `CONTRIBUTING.md`, `docs/workstation-setup.md`, and `README.md` |
| Documentation authoring procedure | `docs/authoring-guide.md` |
| Governing architecture decision | `.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md` |
| Approved implementation sequence | `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md` |
| S37 implementation provenance | `.vault/exec/2026-07-15-cli-authority-verb-conformance/2026-07-15-cli-authority-verb-conformance-W02-P06-S37.md` |
| Independent S37 findings | `.vault/audit/2026-07-16-cli-authority-verb-conformance-s37-auth-cutover-audit.md` |
| Current public application authority | `src/cadrumo/application/auth/__init__.py` |
| Current CLI entrypoint | `src/cadrumo/entrypoints/cli/_config/_auth.py` |

Authentication custody terms have the following meanings in this reference:

- **Target bucket**: the profile bucket whose authentication state and
  provider artefacts the operation may access.
- **Provider scope**: one explicit provider, all known providers, or the
  configured provider when neither selector is supplied.
- **Persisted session**: the bucket-routed provider session object used for
  local AEAT session reuse.
- **Acquisition lock**: the bucket-routed provider lock that serializes live
  session acquisition.
- **Certificate source**: a named certificate registration in `AuthState`.
- **Certificate secret**: the source's secret in canonical bucket secure
  storage. Secret values never enter workflow state or events.
- **Workflow projection event**: the compact auth event stored in
  `WorkflowState.bucket_events`.
- **Append-only bucket event**: the typed durable event stored through
  `BucketEventHistoryRepository`.
- **Cleanup intent**: the secret-free durable `AuthCleanupIntent` that makes
  logout or reset resumable after external cleanup starts.

The remaining sections retain the wider campaign source map. Historical ADRs,
audits, and execution records describe the state inspected at their recorded
revision; they do not override the current implementation authority table.

## Summary

Reference revision:
`87b69b735adeefc9f35ad630e6fd81624c61a0ca`, inspected 2026-07-15.
None of the named production source files had a worktree diff during the audit.
The live CLI materialized to 68 groups and 282 unique leaves with no duplicate
registered path.

Mandatory Vaultspec-RAG searches covered profile selection and custody,
passphrase and recovery vocabulary, auth sessions and locks, certificate secret
resolution, reset/repair overlap, ledger evidence policy, and modelo audit
replay.  Exact source tracing followed the semantic results.

## Canonical authority map

### Active-profile pointer and destructive profile lifecycle

Current duplicate CLI call graph:

```text
config lock ------------------+
                              +--> logout_active_profile
config profile logout --------+       +--> _clear_active_profile_pointer
                                             +--> pointer_path(...).unlink()
```

Source locations:

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py:56-91`
- `src/cadrumo/entrypoints/cli/_config/__init__.py:928-964`
- `src/cadrumo/application/user_profile/_orchestration.py:441-447`

Pointer writes are split across:

- `src/cadrumo/application/user_profile/_orchestration.py:124-140`
- `src/cadrumo/application/user_profile/_orchestration.py:255-268`
- `src/cadrumo/application/user_profile/_orchestration.py:450-489`
- `src/cadrumo/application/user_profile/_profile_repository.py:629-662`
- `src/cadrumo/application/user_profile/_profile_repository.py:881-914`
- `src/cadrumo/application/workflow/_profile_health.py:228-245`

Selection uses the atomic core `write_pointer`; rollback restoration and clear
have independent direct filesystem implementations.  The target authority is
one reentrant application profile-pointer transaction service in
`application/user_profile/_profile_pointer_transaction.py`, backed only by the
core atomic pointer and lock facades.  Repository, cold-start orchestration,
and profile health delegate to it, preserving byte-exact failed-create
rollback without a repository-to-orchestration import.

S26 exposes the core lock primitive through the lazy `cadrumo.core` facade and
the transaction entry point through the `application.user_profile` facade, so
profile health does not import the private implementation module.  It removes
the orchestration-only write, clear, capture, and restore helpers.  Command-line
interface tests seed exceptional pointer states through the public core facade;
their three private-import debt records and the obsolete
orchestration direct-write inventory exception are deleted in the same step.

#### S24 active-profile pointer authority

Scope: S24 makes core pointer mutation byte-preserving and crash-resistant. It
defines core filesystem primitives, completes the hardened byte writer, and
adds public exports. Caller routing, lifecycle policy, creation ordering, and
rollback concurrency policy remain later work.

The current text capture and restore paths can't capture arbitrary bytes.
Payloads that aren't valid Unicode Transformation Format 8-bit (UTF-8) raise
`UnicodeDecodeError`. Universal-newline decoding can also normalize exact line
endings. Direct text restore can leave a partially written pointer file after
an interruption. Direct unlink without a parent-directory sync can leave
pointer removal non-durable after a crash.

The *active-profile pointer* is the file resolved by `pointer_path(root)`. A
*captured pointer* is its complete byte payload, or `None` when the file is
absent. Parsed pointer content remains the domain of `read_pointer(root)`.
Filesystem ownership belongs in `core/_bucket_pointer_io.py`; hardened write
machinery remains in `core/atomic_write.py` and `core/locks.py`.

The current core application programming interface (API) is in
`core/_bucket_pointer_io.py`:

- `pointer_path` occupies lines 37-46.
- `read_pointer`, which performs strict parsing, occupies lines 49-76.
- `resolve_active_bucket_id` occupies lines 79-120.
- `require_active_bucket_id` occupies lines 123-153.
- Deterministic atomic `write_pointer` occupies lines 155-186.

The API has no byte capture, restore, or clear primitive. Existing read
semantics remain unchanged for `config.py`, profile health, `ProfileRepository`,
storage write policy, and authentication scope.

Duplicate mutation owners remain outside core:

- `_orchestration.py` owns `_clear_active_profile_pointer`, text capture, and
  direct text restore or unlink.
- `_profile_repository.py` owns text capture, direct text restore or
  unlink, and direct clear.
- `_profile_health.py` owns another direct unlink path.
- `ProfileRepository` invokes these paths during create, delete, and select.
- Command-line interface (CLI) tests import private orchestration helpers. The
  imports remain recorded in `dev/import_hygiene_test_debt.json` at lines
  273-289.

S24 adds this minimal API:

```python
capture_pointer(root) -> bytes | None
restore_pointer(root, captured: bytes | None) -> None
clear_pointer(root) -> None
```

`capture_pointer` uses `read_bytes`. It preserves the complete payload byte for
byte. `capture_pointer` returns `None` when the pointer is absent.

When `captured` is `None`, `restore_pointer` calls `clear_pointer`. When
`captured` contains bytes, `restore_pointer` calls
`atomic_write_hardened_bytes`. S24 first makes that writer loop over a
`memoryview` until every byte is written instead of assuming one `os.write`
call consumes the full payload.

The hardened path uses `O_EXCL`. On Portable Operating System Interface (POSIX)
systems, it creates staging files with mode `0o600`. Where the operating system
exposes `O_NOINHERIT` or `O_CLOEXEC`, the writer also marks file descriptors
non-inheritable. It syncs the staged bytes, replaces the destination, and
requests a parent-directory sync.

`clear_pointer` treats an absent file as success. After a successful unlink,
it calls `fsync_parent_dir`. `write_pointer` uses the same hardened byte path,
while retaining its existing deterministic serialization. S24 exports the new
functions from `_bucket_pointer_io.py` and the lazy `cadrumo.core` facade.
Imports stay deferred to avoid the `Settings` bootstrap cycle.

S25 adds interruption and exact-byte tests. S26 adds the neutral pointer
transaction service and routes orchestration through it. S27 changes
`ProfileRepository` to use the same transaction, and S28 changes profile
health to use it. S29 tests repository concurrency, and S30 tests
active-profile resolution. S24 doesn't reorder profile creation.

#### S26-S28 reentrant pointer transaction policy

The transaction locks the sidecar derived from `pointer_path(root)`.  Its
in-process owner key is the resolved storage root plus process and thread
identifiers.  Re-entry with that exact key increments a depth counter and does
not reacquire the operating-system lock; another thread or process waits only
for the configured bounded interval.  Failure to acquire the lock raises the
typed contention failure and performs no pointer mutation.  There is no
unlocked fallback.
While the owning thread has a nonzero depth, a nested request for another
canonical root is rejected rather than acquired.  An inherited ownership
record whose process identifier does not match, including state observed after
`fork`, fails closed instead of reusing the parent's ownership.

`profile_create_storage_span` acquires this transaction before any
bucket/session/repository lock and holds it continuously while it captures the
prior bytes, writes the provisional profile, creates storage, registers the
profile, and commits the selection.  Repository calls nested within that span
reuse the same-root, same-process, same-thread ownership.  The fixed lock order
is pointer transaction first, then bucket/session/repository; a caller holding
a later lock must not acquire the pointer transaction.

Both rollback and failed-create cleanup run inside the still-owned transaction
for every `BaseException`, including interruption and process-exit exceptions
that reach Python cleanup.  Rollback restores the captured bytes through the
core atomic primitive before releasing the outermost transaction, then
re-raises the original exception.  This removes the compare-before-restore
race: every live repository, orchestration, and health writer must acquire the
same sidecar before it can select, restore, or clear.

The operating system releases the sidecar lock after a process crash, but a
crash cannot execute rollback or artifact cleanup.  Atomic replacement still
prevents a torn pointer file; a byte-complete provisional pointer can remain
for health and repair to diagnose.  S26 alone establishes only orchestration
conformance.  The global serialized-writer claim becomes true only after S27
routes `ProfileRepository` and S28 routes profile-health repair through this
same service.

`fsync_parent_dir` never raises an exception. If `os.O_DIRECTORY` is
unavailable, it returns without syncing. If opening, syncing, or closing the
directory fails, it logs and suppresses the error. Python on Windows doesn't
expose `os.O_DIRECTORY`, so S24 doesn't claim cross-platform directory
durability.

`reset_config(PROFILE|ALL)` at
`src/cadrumo/application/config_reset.py:165-218` deletes profile lifecycle rows
and bucket directories without clearing the active pointer and without using
`BucketMaintenanceService.delete`.  The canonical deletion policy at
`src/cadrumo/application/bucket_maintenance/_service.py:267-353` owns active
bucket refusal, retention-floor assessment and override, tombstone and manifest
updates, and ordered `PROFILE_TOMBSTONED`/`BUCKET_DELETED` events.  A real
storage probe confirmed that PROFILE reset can leave the pointer naming a
deleted bucket.

Required real-behavior tests: create/switch/logout across a fresh process;
failed-create byte-exact pointer rollback; active and inactive delete/reset;
retention refusal/override; PROFILE and ALL reset ending with no dangling
pointer; interruption-safe pointer replacement.

### Sandbox selection

`config switch` at `src/cadrumo/entrypoints/cli/_config/_custody.py:16-68` and
`config profile sandbox use` at
`src/cadrumo/entrypoints/cli/_config/_sandbox.py:215-265` both call
`select_profile_with_lifecycle_span`.  The latter adds a sandbox prefix and
namespace check.  `switch` is the accepted selector; add an explicit sandbox
short-name resolution contract if required, then remove sandbox `use`.

### Authentication logout and reset authority

#### Canonical mappings

Each command row uses the same lookup format. "Durable events" names both the
workflow projection action and the typed append-only bucket event where both
exist.

| Operator command | Public application service | Preserved state | Removed state | Target and provider scope | Durable events | Implementation location | Verification location | Release status |
|---|---|---|---|---|---|---|---|---|
| `aeat config auth logout [--provider PROVIDER\|--all]` | `logout_operator_auth` | Provider configuration, certificate path and sources, certificate secrets, acquisition locks, unrelated providers, and every unrelated bucket | Persisted sessions in scope; current authenticated timestamp and subject when the versioned configured provider remains the cleanup target | CLI resolves the active bucket. The application service also accepts `target_bucket_id` without changing the active pointer. Provider scope is explicit, all known providers, or the configured provider. | `auth.session.cleared`; `AUTH_SESSION_CLEARED` | `src/cadrumo/application/auth/_operator.py`, `src/cadrumo/application/auth/_operator_scope.py`, `src/cadrumo/application/auth/_sessions.py`, and `src/cadrumo/application/auth/_mutation.py` | `src/cadrumo/application/auth/tests/test_operator_storage_session.py`, `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`, and `src/cadrumo/application/tests/test_cli_workflow_verification.py` | S37 accepted. The full campaign plan governs release; S37 audit-derived gates include `config_reset.py` composition and certificate-secret event recovery. |
| `aeat config auth reset [--provider PROVIDER\|--all] --yes` | `reset_operator_auth` | Unrelated provider configuration, unrelated certificate custody, non-auth bucket state, the active-profile pointer, and every unrelated bucket | Provider configuration in scope, persisted sessions, acquisition locks, certificate path, targeted certificate-source registrations, and their canonical secure-storage secrets | CLI requires `--yes` and resolves the active bucket. The application service accepts `target_bucket_id`. Certificate sources and secrets are reset only when certificate custody is in scope. | `auth.provider.cleared`, `auth.session.cleared`, `auth.lock.cleared`, and `auth.certificate_source.removed`; typed `AUTH_PROVIDER_CLEARED`, `AUTH_SESSION_CLEARED`, `AUTH_LOCK_CLEARED`, `AUTH_CERTIFICATE_SOURCE_REMOVED`, and `AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED` | `src/cadrumo/application/auth/_operator.py`, `src/cadrumo/application/auth/_operator_scope.py`, `src/cadrumo/application/auth/_sessions.py`, `src/cadrumo/application/auth/_acquisition_lock.py`, `src/cadrumo/application/auth/_certificate_sources_operator.py`, and `src/cadrumo/application/auth/_mutation.py` | `src/cadrumo/application/auth/tests/test_operator_storage_session.py`, `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`, `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`, and `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py` | S37 accepted. The full campaign plan governs release; S37 audit-derived gates include S62-S64 composition and certificate-secret event recovery. |

#### Custody and persistence boundaries

- `active_profile_storage_span` binds repository and secure-object access to the
  explicit target bucket or the resolved active bucket. A nested target
  operation restores any unrelated ambient bucket session after completion.
- `auth_mutation_span` is the single reentrant per-bucket auth mutation lock.
  Configure, login, certificate source and secret mutations, logout, and reset
  use this boundary.
- `WorkflowStateRepository.update_with_bucket_events` prepares auth state and
  append-only bucket events from one revision. Its
  `update_with_writes` boundary commits the compare-and-swap writes in one SQL
  unit of work.
- Logout and reset persist a secret-free cleanup intent before deleting
  external session, lock, or secret artefacts. A matching command resumes the
  operation. Other auth mutations fail closed while the intent remains.
- Provider selection is mutually exclusive: `--provider` and `--all` cannot
  appear together. Without either option, the configured provider is the
  scope. A missing configured provider is a typed refusal.
- Session objects and acquisition locks use both bucket and provider identity.
  Logout removes session objects only. Reset removes both session objects and
  acquisition locks.
- Certificate cleanup uses the source registrations captured by the reset
  intent. The intent records source identity and registration timestamps but
  never secret values.
- `WorkflowState.bucket_events` remains the compact workflow projection.
  `BucketEventHistoryRepository` is the append-only event authority. Auth
  event IDs derive deterministically from the bucket, type, timestamp, actor,
  object, and secret-free payload, so recovery does not append duplicates.

#### Remaining `config_reset.py` duplicate

In the committed S37 baseline,
`src/cadrumo/application/config_reset.py` remains a live parallel auth writer.
Its `ConfigResetScope.AUTH` and `ConfigResetScope.ALL` branches replace
`AuthState()` directly and report `removed_auth_session=True`. They do not call
`reset_operator_auth`, remove persisted provider sessions, clear acquisition
locks, remove certificate-source secrets, or emit the canonical auth events.

The approved plan assigns closure to `W02.P05.S62` through `W02.P05.S64`:

| Step | Required authority change | Owner location |
|---|---|---|
| `W02.P05.S62` | Replace the flat scoped reset with resumable start, status, and resume operations | `src/cadrumo/application/config_reset.py` |
| `W02.P05.S63` | Serialize targets and persist reset decisions before mutation | `src/cadrumo/application/config_reset.py` |
| `W02.P05.S64` | Invoke target-scoped `reset_operator_auth` before target deletion | `src/cadrumo/application/config_reset.py` |

This sequencing is a binding pre-release restriction. Candidate worktree edits
do not close it: the branch must not be released, tagged as single-authority
authentication, or used as proof of duplicate closure until S62-S64 are
verified and committed with the direct `AuthState()` reset path removed.
Procedures for operating the future resumable reset belong in operator how-to
documentation, not in this Reference.

#### Supersession and semantic-search status

The former `clear_operator_auth` graph and `aeat config auth clear` command are
retired. `logout_operator_auth` and `reset_operator_auth` supersede that graph.
Historical ADRs, audits, research, and execution records may retain the old
names as revision evidence. They are not current implementation declarations.

Generated terminology and static reference artefacts can still contain the
retired spelling until their assigned campaign steps run. After those
artefacts and this reference are indexed, refresh the Vaultspec-RAG index. A
fresh auth-authority search must return the logout/reset services and this
section as the current authority. Historical results may retain the old token
only when their document type and date identify them as historical evidence.

#### Real-behavior and duplicate checks

The verification map is:

| Contract | Real-behavior location |
|---|---|
| Logout preserves provider and certificate custody while clearing real sessions | `src/cadrumo/application/auth/tests/test_operator_storage_session.py` |
| Reset removes scoped provider state, sessions, locks, registrations, and secure-storage secrets | `src/cadrumo/application/auth/tests/test_operator_storage_session.py` |
| Explicit target operations preserve unrelated bucket state and ambient sessions | `src/cadrumo/application/auth/tests/test_operator_storage_session.py` and `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py` |
| Cleanup survives real repository failure and appends events once | `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py` |
| Acquisition-lock cleanup is target-scoped and idempotent | `src/cadrumo/application/auth/tests/test_acquisition_lock.py` |
| CLI verbs, provider help, payloads, and destructive confirmation match the backend | `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py` and `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py` |
| Workflow projection order is configure, logout, then reset | `src/cadrumo/application/tests/test_cli_workflow_verification.py` |
| Revision-aware secure-object persistence rejects stale writes | `src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py` |

Current-source duplicate checks cover:

- definitions and imports of `clear_operator_auth` and `AuthClearResult`;
- executable CLI registration, schema keys, write policy, risk metadata, and
  help entries for `config.auth.clear`;
- direct `AuthState()` replacement in production reset services;
- direct persisted-session, acquisition-lock, and certificate-secret deletion
  outside the canonical auth application services; and
- auth event construction outside `src/cadrumo/application/auth/_mutation.py`.

Historical `.vault` records are excluded from executable-token checks. Generated
artefacts are tracked separately until their assigned regeneration steps land.

### Certificate credential resolution

The earlier keyring-or-secure-storage graph is superseded. Current source
declares encrypted secure storage as the sole named certificate-secret backend;
the independent master-key OS-keyring custody backend is a separate concern.

Current authority and remaining event-recovery gap:

```text
certificate source select --> AuthState active source and certificate path

certificate secret set/remove --> SecureStorageCertificateSecretBackend
                              --> SecretStore mutation
                              --> append-only certificate-secret event
                                  [ordinary set/remove lacks recovery between stores]

resolve_active_certificate_credentials
  --> selected source path
  --> selected source secret from secure storage
  --> auth status, test, and login credential scope
```

Sources:

- `src/cadrumo/application/auth/_certificate_sources_operator.py`
- `src/cadrumo/application/auth/_certificate_secret_backend.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`

The sole-backend and credential-resolution direction is current. The open HIGH
finding is narrower: ordinary secret set/remove changes the file-backed
`SecretStore` before its SQL-backed append-only event is committed. Expanded
plan rows `W02.P07.S48`, `W02.P07.S51`, and `W04.P13.S118` require a
secret-free durable intent or outbox and real failure/retry proofs so the
original event kind and timestamp are recovered exactly once.

### Data reset and quarantine

Exact call graph:

```text
config reset --scope data -----+
                               +--> quarantine_unreadable_secure_objects
config repair quarantine ------+
```

Sources:

- `src/cadrumo/application/config_reset.py:196-203`
- `src/cadrumo/entrypoints/cli/_config/_repair_cli.py:77-162`
- `src/cadrumo/application/diagnostics.py:1108-1175`

The diagnostics quarantine service remains canonical.  Remove DATA reset; ALL
may compose the same service once.  Tests require a real unreadable
secure-object row, a non-mutating preview, exactly one quarantine copy and one
event/report.

### Ledger evidence

```text
ledger attach
  +--> attach_manual_transaction_evidence
       +--> refuses implicit replacement
       +--> update_manual_transaction_fields
            +--> atomic catalogue and event write

ledger link --evidence-id
  +--> update_manual_transaction_fields directly
       +--> bypasses attach replacement policy
```

Sources:

- `src/cadrumo/application/ledger/_actions_manual.py:177-240`
- `src/cadrumo/application/ledger/_actions_manual.py:457-524`
- `src/cadrumo/application/ledger/_actions_manual.py:618-694`
- `src/cadrumo/application/ledger/_actions_manual.py:899-936`
- `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:134-171`
- `src/cadrumo/entrypoints/cli/_ledger.py:925-1026`

`attach_manual_transaction_evidence` owns evidence policy.  `ledger link`
remains for invoice relations but must drop or delegate `--evidence-id`.  If
the combined invoice-plus-evidence input remains, move it into one atomic
application operation because its current sequential writes can partially
commit.

Required real-behavior tests prove implicit replacement refusal, explicit
replacement lineage if introduced, referenced-evidence existence, and
all-or-nothing combined mutation.

### Modelo audit check and replay

`EvidenceBundleService.replay` at
`src/cadrumo/application/evidence/_service.py:380-397` is exactly
`return self.check(...)`.  CLI handlers only wrap the same result differently:

- `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py:94-133`
- `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py:195-234`

The accepted evidence-bundle contract requires stored-input replay and distinct
match, degraded, and corrupt outcomes.  Remove the leaf until a distinct
`EvidenceReplayService` exists, or implement that service before retaining the
name.  `check` remains the integrity owner.

Required tests make payload mutation fail check, make an unavailable payload
incomplete, independently reach all replay outcomes, and assert the required
replay event only for actual replay.

### Profile export and subject access

One serializer already exists at
`src/cadrumo/application/user_profile/_bundle.py:159-216`, but the CLI duplicates
session scope, resolution, serialization, event emission, directory creation,
and cleartext output:

- subject access: `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py:68-173`
- portable export: `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py:202-333`
- near-identical closures: lines `118-148` and `275-305`

Create one application `export_profile_bundle` service with a typed purpose and
atomic target write.  The subject-access leaf may remain for legal
discoverability.  Derive `_SAR_DATA_CATEGORIES` from the bundle schema rather
than maintaining a second projection.

Required tests compare cleartext bundle bytes for the same snapshot, assert one
purpose-bearing event, cover encrypted roundtrip, prove failure leaves no
partial target, and reconcile the subject-access catalogue to actual fields.

### Custody passphrase and recovery

`rekey_secret_store` and `recover_secret_store` at
`src/cadrumo/application/user_profile/_custody.py:163-213` share a final rewrap
primitive but are not duplicates.  The former authenticates with current
custody, the latter with the recovery mnemonic.  Preserve distinct authorization
and, if useful, extract only a small rewrap helper.

The current CLI registration lives at
`src/cadrumo/entrypoints/cli/_config/_custody_secret.py:94-275`.
`show-recovery` is overloaded: it reports status, creates recovery material when
missing, and rotates it under `--rotate`.  The target family separates
`recovery status`, `recovery create`, `recovery rotate`, and `recovery verify`;
the already accurate flat `recover` action remains.  Create/rotate stage and
display a candidate, require no-echo full confirmation, and commit only after
verification so the previous recovery envelope survives failure.  Verify and
recover accept no mnemonic argv value; they use a no-echo prompt or an explicit
stdin automation mode.  `rekey` becomes `passphrase change` because the master
key is preserved, and file custody is a typed precondition for all passphrase
and mnemonic operations.

Required tests prove current-passphrase authorization for change, mnemonic
authorization for recovery, preservation of master-key fingerprint and stored
data, preservation of the old mnemonic on failed rotation, invalidation only
after confirmed rotation, absence of mnemonic material from argv/errors/logs,
and post-restart behavior for file, keyring, AUTO, and unsecured custody.

### Import-linter infrastructure

The research snapshot found `.importlinter` rooted at the retired `aeat`
package and a vacuous ignore-ledger parser. Wave `W01` repaired that
infrastructure before the CLI authority work began. The live configuration now
declares `root_package = cadrumo`, retains all five architecture contracts, and
contains no broad exemption added for the auth remediation.

`src/cadrumo/tests/test_importlinter_ledger.py` now parses `cadrumo.*` edges,
requires both the complete and layered ledgers to be non-empty, verifies that
referenced modules resolve on disk, and ratchets the reconciled ceilings at
199 application-to-adapter edges, 78 application-source wildcard edges, and 2
test-only domain-to-adapter edges. Those ceilings may decrease but may not be
raised.

The latest S37 corrective run analyzed 3,427 files and 16,219 dependencies:
all five contracts were kept and zero were broken. The S37 remediation removed
auth adapter exemptions rather than adding architecture debt. A fresh uncached
five-contract run and the non-vacuous ledger tests remain mandatory at final
campaign verification.

### Canonical hashing

Canonical implementation: `src/cadrumo/core/hashing.py:32-40`.

Residual exact implementations:

- `src/cadrumo/entrypoints/mcp/_telemetry.py:79-81`
- `src/cadrumo/application/modelo/_review_package_recipient_registry.py:108-110`

Both consumers may import core without violating layer direction.  Delegate the
telemetry wrapper to `sha256_hex` and replace the recipient fingerprint body
with the same helper.  Tests assert digest parity through the real public
consumers rather than mirroring the algorithm.

## External command references

- GitHub active account switch: `https://cli.github.com/manual/gh_auth_switch`
- Docker context selection: `https://docs.docker.com/reference/cli/docker/context/use/`
- Kubernetes context selection: `https://kubernetes.io/docs/reference/kubectl/generated/kubectl_config/kubectl_config_use-context/`
- Bitwarden lock/logout state distinction: `https://bitwarden.com/help/cli/`
- 1Password signout: `https://www.1password.dev/cli/reference/commands/signout`
- Restic password change: `https://restic.readthedocs.io/en/stable/070_encryption.html`
- HashiCorp Vault rekey semantics: `https://developer.hashicorp.com/vault/docs/commands/operator/rekey`
- Restic check and repair: `https://restic.readthedocs.io/en/stable/077_troubleshooting.html`
- Git replay semantics: `https://git-scm.com/docs/git-replay.html`

These are vocabulary comparators only.  Bitwarden is the strongest lock/logout
comparator because it explicitly represents both states.  Vault is an
anti-comparator for `rekey`: it changes key-share material, illustrating why the
term misstates this project's wrapping-only behavior.

## Blast radius and gates

Approximate non-generated file counts from the audit are: lock/logout 11,
sandbox use 9, reset/quarantine 27, audit replay 11, ledger link/attach 36,
profile export/SAR 28, custody commands 18, and certificate-secret surfaces 14.
The implementation sweep must cover handlers and application facades, typed
payloads and JSON schema operation mappings, all four locales, operator help and
risk tables, error-registry suggestions and `next_action` values, direct
real-behavior tests, Sphinx CLI references and static CLI tree, how-to sequences,
and any MCP dispatch or command metadata mirrors.

No compatibility alias, deprecation spelling, shadow command, or retired-verb
ledger may survive.  Machine envelope tokens may remain stable only where the
accepted operator-surface decision already permits a documented path-key
override and the token does not create an operator-visible command.

Verification must include a green, uncached import-linter run before feature
work, the focused real-storage tests for every authority
above, live command-tree materialization, documented-command and JSON-schema
conformance, locale coverage, clone audit, the feature-surface quality gate, and
the full project gates attributable to this campaign.
