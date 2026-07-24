---
tags:
  - '#adr'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-24'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-research]]"
  - "[[2026-07-15-cli-authority-verb-conformance-reference]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr]]"
  - '[[2026-07-24-profile-login-session-adr]]'
---

# `cli-authority-verb-conformance` adr: `Single backend authorities and cost-aware CLI verbs` | (**status:** `accepted`)

## Amendment note (2026-07-24)

The profile-session verb set in Decision 2/3 is amended by the accepted
`2026-07-24-profile-login-session-adr` under an explicit operator override:
`aeat config switch NAME` and `aeat config profile logout` are replaced by
`aeat config login [NAME]` and `aeat config logout`. The strong session-close
semantics defined here are upheld verbatim by the replacing `logout`; the
one-verb, no-alias, hard-cutover rule is upheld (`switch` is deleted, not
aliased). Every other decision in this ADR remains authoritative.

## Problem Statement

The live CLI has no duplicate registered paths, but it exposes several different
paths for the same operation and several paths that mutate the same state under
different policy.  These are maintainability and correctness defects: profile
reset can delete the active bucket while leaving a dangling pointer and bypass
retention policy; auth reset claims to remove sessions without deleting them;
named certificate secrets do not feed live login; ledger evidence can bypass
attach safety; audit replay is exactly audit check; and profile export is
orchestrated twice in the CLI.

Some custody words also misstate their behavior.  `lock` performs logout,
`rekey` preserves the master key and only changes its passphrase wrapping, and
`show-recovery` may create or rotate recovery material.  A broad rename sweep
would be expensive and destabilizing, so this ADR chooses only changes whose
semantic or deduplication value exceeds their migration cost.

The audit also found two degraded governance surfaces.  The import-linter gate
cannot build its graph because its configured root is the retired package
`aeat`, while the duplication report can falsely report GREEN on Windows after
jscpd scans no production files.  Hashing duplication is also substantially
broader than the earlier two-body count: eighteen exact production one-shot
SHA-256 bodies and four additional reducible hash bodies remain outside the
canonical helper.  Further authority duplication exists in storage namespace
metadata, filed-capture persistence and finalization, LLM review orchestration,
registry query projections, and profile export/subject-access publication.
These are within scope because a CLI hardening campaign cannot rely on
false-green architecture or duplication evidence or preserve parallel backend
authorities beneath a simplified command surface.

## Prior-decision reconciliation

This ADR upholds the accepted `cli-operator-surface` one-verb, hard-cutover,
intent-vocabulary rule and the `profile-state-aggregate` sole-writer rule.  It
amends, rather than silently coexisting with, three accepted grammars:

- The `config-auth-shape` decision's single broad `auth clear` verb is replaced
  by distinct session `auth logout` and provider-custody `auth reset` intents.
- The `secure-backend-passkey-custody` decisions that exposed `config lock`,
  `config rekey`, flat `show-recovery`/`verify-recovery`, and their exact
  lifecycle semantics are amended to the target custody grammar below.  Flat
  `config recover` remains because it already names its intent accurately.
- The `evidence-bundle-shape` decision's public replay leaf is deferred and
  removed from the shipped surface until a distinct stored-input replay service
  satisfies that decision's match/degraded/corrupt contract.  The evidence
  model and export/check decisions remain accepted.

It also upholds the accepted import-linter gates-ratchet and test-carveout
decisions: production construction edges remain individually pinned, broad
application wildcards remain forbidden, and real-adapter test seams may cross
through a shared `cadrumo.tests` helper only by a live, narrow route.

This amendment also corrects this ADR's own accepted certificate-keyring
migration language. Cadrumo is unreleased, so `no-legacy-compatibility`
governs unconditionally. The unreleased certificate keyring backend, selector, schema, tests, and
documentation are deleted rather than migrated, reconciled, probed, cleaned up
through a compatibility path, or preserved behind a fallback.  The native
Windows Credential Manager, macOS Keychain, and Linux Secret Service migration
jobs required by the previous text are withdrawn.  This correction does not
remove or weaken the separate master-key OS-keyring custody backend, which is
not a certificate-secret backend.

The accepted secure-storage architecture and security-review decisions already
make `STORAGE_NAMESPACE_REGISTRY` the authority for storage namespace metadata.
Duplicate namespace literals and a false-green adoption test are implementation
drift, not competing accepted architecture.  This ADR makes that existing
authority operational across domain, application, and adapter consumers.

The accepted registry-authority-flow decision remains authoritative for
revision selection.  Scoped and unscoped resolution remain distinct; only
their post-resolution report projections are consolidated.  The accepted
profile-portability decision remains authoritative for portable bundle
contents, while this ADR assigns publication, durability, event sequencing, and
subject-access routing to one application authority.  The sealed full-profile
recovery archive remains a different product and custody contract.

The earlier research and reference documents were revision-bound audit inputs.
The current-tree semantic and exact-source audit supersedes their counts where
the repository has proven broader duplication: eighteen exact one-shot hashes,
four additional reducible hash bodies, and the authority overlaps specified
below.  Filed-capture finalization, LLM review routing, registry report
projection, and duplication-runner ownership were not settled by a conflicting
accepted ADR and are new decisions within this campaign.

These are partial amendments; the parent ADRs remain authoritative for every
unmentioned decision.

## Considerations

- The accepted operator-surface rule requires one guessable, intent-named verb
  per operation and hard replacement without aliases or compatibility shadows.
- A command alias is not the only duplication risk.  A second writer with
  weaker guards is more dangerous than two functions with similar text.
- `ProfileRepository` and bucket maintenance are already accepted as the
  profile aggregate and destructive lifecycle authorities.
- `clear_operator_auth` already owns provider state, persisted sessions,
  acquisition locks, and auth events.
- The accepted evidence-bundle decision describes real stored-input replay;
  the current check alias does not satisfy it.
- Both `switch` and `use` are common CLI vocabulary.  The project already chose
  `switch`, so renaming it again would create cost without semantic gain.
- Named certificate secrets have never shipped under a released durability
  contract.  Secure storage is their sole authority; retaining migration or
  cleanup logic for the deleted certificate keyring backend would violate the
  active pre-release compatibility regime.
- The repository is pre-release and forbids shims.  Documentation, locales,
  schemas, command mirrors, and tests move atomically with each hard change.
- The shared worktree contains unrelated active campaigns.  Implementation must
  preserve their changes and use path-scoped commits and gates.
- Similar text is not sufficient reason to consolidate different policies.
  Consolidation applies only where the audited paths share one semantic
  authority and substitutable behavior.
- A duplication tool that did not observe the production tree cannot establish
  zero duplication.  Unavailable, failed, timed-out, or unparseable evidence is
  distinct from an observed zero result.
- Canonical hashing owns byte-to-digest mechanics.  Callers continue to own the
  semantic byte projection and domain separation that define an identifier.

## Considered options

### Option A: rename operator verbs only

Rejected.  It is the smallest textual diff but leaves destructive reset,
certificate login, evidence replacement, pointer writes, and profile export
with parallel authorities beneath cleaner names.

### Option B: consolidate backend writers but retain every command as an alias

Rejected.  It fixes correctness but violates the accepted one-verb rule and
keeps documentation, tests, locales, and future maintenance multiplied.

### Option C: single backend authorities plus a minimal hard-cutover verb set

Chosen.  Repair the authorities first, remove exact duplicate doors, and rename
only custody/auth words that materially conflate states or misdescribe
security behavior.

### Option D: preserve or migrate the unreleased certificate keyring backend

Rejected.  The live compatibility regime is `PRE_RELEASE`, so no released data
or caller requires preservation.  A backend selector, migration, reconciliation
probe, fallback, legacy cleanup branch, or native migration matrix would
maintain obsolete app-written state and contradict the active
delete-not-migrate rule.  Named certificate secrets use secure storage only.
This decision is independent of the retained master-key OS-keyring custody
backend.

### Option E: remove the whole `config reset` surface

Rejected.  One confirmed all-profile reset is a useful operator intent, but it
must be a crash-resumable composition of canonical auth, pointer, retention,
and bucket-deletion services.  Separate PROFILE and ALL scopes are rejected as
duplicates once DATA and AUTH move to their canonical doors.

## Constraints

- No CLI or backend-authority wave after Wave 0 begins until `.importlinter`
  names `cadrumo`, the full uncached graph builds, every existing contract is
  green, and the ledger ratchet parses a non-empty Cadrumo inventory at its
  reconciled live ceilings.  Contract weakening, ceiling increases, and broad
  production ignores are forbidden.
- CLI handlers remain transport only.  They do not perform direct store writes,
  multi-step business transactions, schema policy, or recovery policy.
- Active-profile pointer capture, restore, select, and clear use one atomic
  application/core boundary.  Failed create must restore prior bytes exactly.
  Every participating writer uses the same bounded, fail-closed pointer
  transaction; no timeout or contention path falls back to an unlocked core
  mutation.
- The single all-profile reset must preflight retention for the whole target
  set, then execute as an idempotent, durable, roll-forward state machine.
  Multi-bucket filesystem deletion is not falsely described as atomic.  A
  crash leaves a typed incomplete operation; read-only status points to an
  explicit confirmed resume from its recorded phase.  It never leaves an
  unreported partial reset.
- Bucket maintenance must expose a public target-scoped deletion assessment,
  and auth must expose target-scoped cleanup.  Bulk reset cannot copy private
  retention logic or switch the global active pointer merely to reach a bucket.
- Auth logout preserves provider configuration.  Auth reset clears provider
  configuration, sessions, acquisition locks, certificate-source registrations,
  and their bound secrets, and emits the established events.
- With neither `--provider` nor `--all`, auth logout/reset targets the currently
  configured provider and refuses if none is configured.  The two options are
  mutually exclusive.  An explicit configured or reserved provider operation
  is idempotent when its target artefacts are already absent; `--all` is the
  only multi-provider sweep.
- Named certificate credentials fail closed when the selected source has no
  bound secure-storage secret.  They do not silently fall back to unrelated
  global credentials.
- Ledger evidence assignment always passes through the evidence policy owner.
  Combined invoice/evidence mutation, if retained, is atomic.
- Subject access remains legally discoverable but cannot own a parallel export
  writer.  Its catalogue derives from the bundle schema or service result.
- Passphrase change and mnemonic recovery retain distinct authorization even
  though they share a rewrap primitive.
- Operation/command tokens affected by this campaign migrate to canonical new
  protocol identifiers with the CLI path.  No old token from a removed spelling
  survives.  Unrelated stable protocol identifiers already documented by prior
  ADRs, such as the profile-history path override, remain unchanged and may
  never render as an operator-visible alias.
- Tests use real services, repositories, encrypted storage, pointer files,
  sessions, locks, certificate payloads, and CLI invocation.  Fakes, mocks,
  monkeypatches, skips, and mirrored business logic are forbidden.
- The unconditional pre-release no-legacy hard cut is binding. Delete the
  certificate keyring backend and every selector, factory branch, schema field, locale,
  test, documentation path, migration, reconciliation, fallback, and
  certificate-specific native integration obligation attached to it.  Do not
  disturb the separate master-key OS-keyring custody implementation.
- `STORAGE_NAMESPACE_REGISTRY` is the sole authority for namespace identifiers,
  schema versions, sensitivity, default keys and key grammars, custody scope,
  and custody policy.  Consumers may use a neutral typed facade where import
  boundaries require it, but may not redeclare registry metadata.
- Filed-capture modes share one latest-observation persistence and finalization
  authority while retaining their explicit fail-fast, best-effort, and strict
  IVA compensation failure policies.
- LLM review orchestration has one application owner and requires typed
  invocation provenance.  Application operations may not default provenance to
  a particular CLI spelling.
- Scoped and unscoped registry revision resolution remain distinct.  Once
  resolution succeeds, shared report shapes use one projection authority.
  Accepted parameters may never be silently ignored.
- Portable profile export and subject access use one durable publication
  service.  A success audit event is emitted only after the destination has
  been atomically published and durably synchronized.
- Exact one-shot SHA-256 and reducible local file-hash mechanics use
  `core.hashing`.  Incremental streams, structured folds, keyed HMAC, HKDF,
  X509 fingerprints, digest-byte checksums, and other semantically different
  cryptographic operations remain distinct.
- Duplication health distinguishes observed zero, observed clones, and
  unavailable or invalid evidence.  Only an observed zero may be GREEN.
- Intentional non-consolidations remain: passphrase change versus mnemonic
  recovery; Google logout versus profile/auth logout; doclink acquisition
  versus canonical attach; sandbox discard versus prune; portable export
  versus sealed archive; evidence export invoking check; ledger list versus
  review read models; auth status versus test; legal aggregation resolver
  families; GROI/NIF oracle authorities; broad Typer templates; recipient
  registry versus replay guard; invoice create versus wizard; scoped versus
  unscoped registry selection; strict IVA compensation persistence versus
  ordinary filed capture; and `classify --auto-split` versus `split --llm`.
- User-facing documentation changes follow the mandatory structured
  documentation workflow and its approval gates.

## Implementation

### Decision 1: restore the architecture gate first

Change the import-linter root package from `aeat` to `cadrumo`, run all
contracts without cache, and repair any genuine boundary or stale-ignore defect
without weakening the architecture.  This is the prerequisite gate for every
subsequent wave.

The corrected-root diagnostic fixes the scope of that repair.  Remove the two
stale `_censo` and `_censo_sync` wildcard entries.  Restore the narrow accepted
shared-fixture route from `core.tests.test_isolation_fixture_state_root_coverage`
to `tests.secure_sql` in the contract that reports that helper-mediated chain.
Remove the dead
`aggregation._irnr_income_ledger -> adapters.persistence.profile.transactions`
edge instead of pinning it: require the already injected transaction repository
Protocol in both the repository-loading function and the public IRNR resolver
constructor so every ledger resolver continues through the source mesh's
single memoized repository.  Remove the genuine type-only
`modelo._verification_actions -> adapters.persistence.profile.invoices` edge by
typing it and the receiving OSS/IOSS resolver against
`InvoiceCatalogueRepositoryProtocol`; verification does not construct that
adapter, so no ignore is authorized.

Retarget `test_importlinter_ledger.py` from `aeat.*` to `cadrumo.*`; its current
empty parse makes every count ratchet vacuous.  Narrow the standing
`diagnostics_run_health -> adapters.**` pin to `adapters.outbound.llm`, then
lower the application-edge, application-source-wildcard, and domain-edge
ceilings from 840/78/70 to the reconciled live counts 199/78/2.  No ceiling may
increase.  No new production pin, wildcard, or contract relaxation is
authorized.  The wave closes only when a fresh uncached process analyzes the
full graph, reports all five contracts kept, and the repaired ledger test proves
that its parsed inventory is non-empty and within those ceilings.

### Decision 2: establish canonical backend authorities

Introduce one atomic active-profile pointer boundary and route repository,
orchestration rollback, logout, repair, delete, and reset through it.
Implement that boundary once in the neutral
`application/user_profile/_profile_pointer_transaction.py` module.  The module
uses the core pointer and lock facades but imports neither orchestration nor the
repository, so orchestration, repository, and profile health depend on it in
one direction.  The core facade exposes the lock primitive required by the
service, and the user-profile facade exposes the application transaction entry
point to cross-package consumers without exposing its private module path.  The
lock target is the sidecar derived from the configured root's active-pointer
path.  Ownership is reentrant only for the same resolved root, process
identifier, and thread identifier; a matching nested acquisition increments an
in-process depth instead of reacquiring the non-reentrant operating-system
lock.  A different thread or process contends for the sidecar for the
configured bounded interval and fails closed when that interval expires.
While a transaction is owned, a nested request from the owning thread for a
different canonical root is rejected rather than acquired.  An inherited
ownership record whose process identifier no longer matches, including after
`fork`, also fails closed instead of reusing the parent's ownership.

Cold-start profile creation acquires the pointer transaction before any
bucket, session, or repository lock and retains it continuously across pointer
capture, provisional selection, storage creation, registration, and final
commit.  Nested repository pointer calls for the same root execute under the
reentrant ownership.  Code that already holds a bucket or storage lock must
not enter the pointer transaction, which fixes the lock order as pointer first,
then bucket/session/repository.  On any `BaseException`, rollback restores the
captured bytes exactly and performs failed-create artifact cleanup before the
outer pointer transaction releases; the original exception is then re-raised.
Successful completion leaves the committed selection in place and releases
the transaction once its reentrancy depth returns to zero.

The transaction serializes cooperating live writers but cannot roll back a
process crash because no Python cleanup handler runs.  The core atomic writer
still prevents torn pointer bytes; a crash may leave a complete provisional
pointer for the existing health and repair path to diagnose.  S26 establishes
the service and routes orchestration, but the single-writer claim is not global
until S27 routes `ProfileRepository` and S28 routes profile-health repair
through the same reentrant transaction.

Profile logout becomes the strong session-close operation: close and zeroise
the active `BucketSession`, clear any OS-keystore session cache entry, release
its lockfile, and clear the pointer.  Idle-timeout auto-lock remains an internal
custody guarantee, while `switch` remains the accepted select-and-unlock
operator intent.  No weaker pointer-only logout or second explicit lock door
survives.

The single reset intent uses a new durable reset-operation record outside the
target bucket directories.  Its target set is every live or tombstoned profile
bucket registered under the configured local storage root, plus a dangling
pointer target for explicit reconciliation; it never addresses the cold
bootstrap/default repository as an implicit substitute.  The record snapshots
target UUIDs and authoritative content/revision fingerprints, approved
retention decisions, the active pointer, and per-target phase without storing
credentials.  The ordered phases are:

1. snapshot targets and refuse a concurrent reset;
2. acquire every target's existing exclusive bucket lock in sorted UUID order,
   call a public target-scoped deletion assessment for every bucket, and refuse
   before mutation if any retention gate is unresolved;
3. clear target-scoped auth sessions, locks, provider state, registered
   certificate sources, and their canonical secure-storage secrets while each
   target remains reachable;
4. strongly logout and clear the pointer when it names a target;
5. delete each bucket through `BucketMaintenanceService`, recording completion
   after each idempotent irreversible transition;
6. mark the operation complete and retain its non-secret audit summary.

After the first irreversible deletion the policy is roll-forward, not rollback.
Before each delete call the journal records `deleting` with the operation id,
target UUID, authoritative content fingerprint, and approved retention
decision.  Bucket deletion accepts that operation id.  On resume, absence
counts as already completed only when the same journal and snapshot prove
ownership of the deletion; generic profile absence remains an error.  A crash
releases OS locks.  Resume reacquires every remaining target lock in sorted
order and rechecks authoritative content/revision fingerprints and retention.
If content changed, the operation pauses and requires renewed `--yes` plus any
retention override/reason before continuing.  Every phase is otherwise
idempotent.  A new reset start refuses while an incomplete record exists and
points to its status and resume commands; status only reports and never resumes.
The CLI reports incomplete versus complete honestly.  Failure-injection,
concurrent-writer, and fresh-process tests cover every phase boundary using
real child processes, locks, and storage failures.

The reset erases target profile buckets, their auth sessions/locks/secrets, and
the active pointer.  Bucket-local workflow projections disappear with their
owning bucket; no post-deletion write targets the cold bootstrap/default route.
It does not invoke quarantine and does not claim to erase logs, user-directed
exports, or external archives.  Quarantine remains exclusively `config repair
quarantine` against an explicitly resolved active profile.
Remove DATA and AUTH as standalone reset scopes because `repair quarantine` and
`auth reset` are their canonical doors.

Refactor the existing broad auth clear code into two public application
operations.  `logout_operator_auth` is session-only: it deletes persisted
sessions in the resolved scope, updates session readiness/timestamps to an
unauthenticated state, and emits session-cleared events while preserving
provider and certificate-source configuration.  `reset_operator_auth` owns
provider configuration, sessions, locks, registered certificate sources, and
bound secrets.  Both accept an explicit bucket target for bulk reset without
switching the global pointer; CLI calls resolve the active bucket once.

Introduce one active-certificate credential resolver consumed by certificate
check, auth status/test, and login.  Named certificate secrets use
selected-profile secure storage only and fail closed when absent.  Delete
`KeyringCertificateSecretBackend`, `CertificateSecretBackendKind.KEYRING`, its
factory branch, certificate-secret `--backend`, and all certificate-specific
keyring service/account, schema, locale, documentation, and test surfaces.
There is no migration, reconciliation, fallback, probe, or deletion path for
values written by the unreleased certificate keyring backend.  This deletion
does not affect master-key OS-keyring custody.

Route all purchase-evidence assignment through the attach policy.  Keep
`ledger link` for invoice relations and remove its evidence option.  If the
combined relation operation remains useful, implement it as one atomic
application transaction.

Move the whole portable profile export transaction into one application
service with a typed purpose distinguishing `portable_transfer` from
`subject_access`.  Both live CLI consumers route through that service; neither
retains independent profile resolution, serialization, publication, category
enumeration, or event emission.

The service serializes writers to the same destination, resolves the payload
and transport, writes a restrictive-permission temporary artefact and fsyncs
its bytes, durably records a non-secret PREPARED operation containing the
destination, purpose, transport, digest, and owned temporary identity, then
atomically replaces the destination and fsyncs its parent directory.  Only
after durable publication does it mark the operation COMPLETED and emit
`PROFILE_EXPORTED`.  Reconciliation of PREPARED state is idempotent: a matching
destination digest completes the operation; otherwise the service safely
retries or removes only its owned unpublished temporary artefact.  It never
records or emits false success.

Subject-access categories derive from the actual portable bundle schema and
registry-selected carried namespaces or from the typed service result, not a
static five-item CLI tuple.  Subject access and cleartext portable export carry
the same handoff and disclosure-risk classification.  The sealed full-bucket
recovery archive remains a separate authority and format.

Delegate all eighteen exact production one-shot SHA-256 bodies to
`core.hashing.sha256_hex`, preserving each caller's existing byte projection,
truncation, and identifier semantics.  The audited bodies are in
`adapters/inbound/declaracion/_parser.py`,
`adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`,
`adapters/outbound/aeat/auth/_clave_movil_support.py`,
`adapters/outbound/llm/_cache.py`,
`adapters/persistence/storage/_rotation.py`,
`adapters/persistence/storage/sql/engine.py`,
`agent/eval/_flywheel.py`, `entrypoints/mcp/_telemetry.py`,
`application/aggregation/_percepciones_observations_repository.py`,
`application/aggregation/_retencion_observations_repository.py`,
the two bodies in
`application/calculations/_observations_repository.py`,
`application/filing/_import.py`,
`application/modelo/_m145_communication_records.py`,
`application/modelo/_review_package_recipient_registry.py`,
`application/storage/calc_sheets/_engine.py`,
`application/workflow/_models.py`, and
`domain/submission/_models.py`.

Reduce four further bodies without changing their semantics:
`core/corpus_manifest/__init__.py` delegates its whole-file digest and length to
`core.hashing.hash_file`; `core/observability/_fingerprint.py` retains its
retry/stability policy while delegating successful file hashing;
`domain/manuals/_fetch.py` delegates local-file verification while retaining
incremental network-response hashing; and
`adapters/outbound/storage/_mirror_manifest.py` constructs the same
domain-separated bytes and delegates their unkeyed digest to `sha256_hex`.
Despite its current name, the last operation is not converted into a keyed HMAC
because that would change object identifiers.

Incremental registry and filing fingerprints, attachment and mirror streams,
observability tree folds, network-response streams, true HMAC, HKDF, X509
fingerprints, BIP39/digest-byte checksums, and other operations requiring
incremental or binary digest behavior remain separate.

`STORAGE_NAMESPACE_REGISTRY` becomes the operational source of truth for every
registered namespace.  Transaction catalogue, participation index, Cl@ve
Móvil/Permanente, profile repositories, calculation observations, LLM usage,
bundle membership, and custody consumers obtain namespace, version, sensitivity,
default-key/key-grammar, and custody metadata from the registered definition or
its neutral typed facade.  Local copies in application, domain, and adapter
modules are deleted.  Registry metadata is corrected where it does not describe
the live object-key shape, including transaction catalogue and optional
calculation-observation member keys.  Distinct namespaces are not merged merely
because some metadata fields match.

The namespace adoption authority covers every production root, including
profile persistence adapters.  It recognizes the live `cadrumo.*` namespace
family, detects duplicate declarations, and proves that consumers bind to the
registered definition rather than merely checking whether a literal appears
somewhere in the registry.

Make `_filed_observation_persistence` the sole owner of latest filed-calculation
observation selection, history ordering, and persistence.  Remove the copied
selector and raw period-token ordering from `_filed_data_capture`.  One typed
capture finalizer receives accumulated observations and an explicit failure
policy and is used by single, bulk, and source capture.  Single and source
capture remain fail-fast for registry-enrollment finalization; bulk capture
continues to accumulate selected failures; the strict IVA compensation-history
path remains separate.  CLI and report wrappers do not become persistence
owners.

Introduce one typed application LLM-review workflow that owns suggestion,
review, apply, reject, auto-split, and saturation routing while calling the
existing canonical persistence primitives.  Invocation origin is required
typed input rather than an application default naming a CLI command.  The CLI
retains grammar, active-profile/repository composition, confirmation,
localization, and rendering.  `classify --auto-split` and `split --llm` remain
separate operator intents because their one-child/no-split behavior differs.

Within `RegistryQueryService`, preserve `_resolve_revision` and
`_resolve_revision_for_scope` as different selection authorities.  Convert
their successful results into one internal typed resolved context, then use one
projection builder for each shared describe, casillas, formulas, and other
provably identical report shape.  Unscoped `as_of` is currently accepted but
ignored by `_resolve_revision`; the contract must either route it through a
real validity authority or remove/reject it.  Silent acceptance is forbidden.
Bindings and single-casilla detail remain separate unless their constraints are
proved substitutable.

### Decision 3: remove duplicate and misleading command doors

The hard-cutover target is:

```text
aeat config switch NAME
aeat config profile logout

aeat config passphrase change [--secrets-stdin]
aeat config recovery status
aeat config recovery create
aeat config recovery rotate
aeat config recovery verify [--secrets-stdin]
aeat config recover [--secrets-stdin]

aeat config auth login
aeat config auth logout [--provider PROVIDER|--all]
aeat config auth reset [--provider PROVIDER|--all] --yes
aeat config auth certificate secret set --name NAME
aeat config auth certificate secret remove --name NAME

aeat config repair quarantine
aeat config reset start --yes [--override-retention --reason TEXT]
aeat config reset status [--operation-id ID]
aeat config reset resume [--operation-id ID] --yes [--override-retention --reason TEXT]

aeat app ledger attach ...
aeat app ledger link ... --invoice-id ...
aeat app modelo audit check ...
```

Remove `config lock`, `config profile sandbox use`, `config rekey`,
`config show-recovery`, `config verify-recovery`, `config auth clear`, the
certificate-secret `--backend` selector, DATA/AUTH reset scopes, `ledger link
--evidence-id`, the flat `config reset --scope ...` spelling, and the current
`modelo audit replay`.  No removed spelling remains as an alias, suggestion
target, hidden registration, or documentation path.

`switch NAME` accepts the same unambiguous UUID or exact operator label returned
by profile listing.  A sandbox is selected by its canonical `sandbox:<name>`
label returned by sandbox listing; a bare short name is not implicitly
namespaced.  UUID/label ambiguity or duplicate labels refuse with the existing
typed selection error.  This preserves sandbox namespace validation without a
second `use` door.

`recovery status` is read-only.  `recovery create` refuses if recovery already
exists.  `recovery rotate` requires existing enrollment.  Create and rotate are
two-phase: stage and display a candidate mnemonic, require a no-echo full
retype/verification, then atomically install the candidate envelope.  The old
envelope remains valid on cancellation, output failure, or verification
failure.  The mnemonic is not repeated after commit.

Create and rotate require an interactive controlling terminal.  The candidate
mnemonic is written directly to that terminal, never stdout or the diagnostic
stream; the final text/JSON success envelope is emitted only after confirmation
and never contains the mnemonic.  Non-interactive create/rotate refuses.  This
is an explicit narrow exception to machine-driven secret enrollment, not an
exception to structured final output.

`recovery verify` validates a mnemonic without changing custody.  Flat
`config recover` remains the recovery action and rewraps the same master key
under a new passphrase.  Neither accepts the mnemonic as an ordinary argv
value.  Interactive use reads it through a no-echo prompt; non-interactive use
requires explicit `--secrets-stdin`.  That mode reads one bounded strict JSON
object from standard input: verify requires `recovery_key`; recover requires
`recovery_key`, `new_passphrase`, and `new_passphrase_confirmation`; passphrase
change requires `current_passphrase`, `new_passphrase`, and confirmation.  No
secret field is echoed, logged, copied to an error envelope, or returned in the
success envelope.  Passphrase change, recovery
create/rotate/verify, and recover operate only when file custody is the resolved
backend (including AUTO resolved to file); keyring, AUTO resolved to keyring,
and unsecured custody refuse with typed remediation.  Passphrase change
requires current custody and preserves the post-restart master-key fingerprint.

With no scope flag, `auth logout` and `auth reset` target the configured provider
and refuse when none is configured.  `--provider` and `--all` are mutually
exclusive.  Logout is idempotent after scope resolution: it removes persisted
sessions, updates workflow session readiness to unauthenticated, and emits
session-cleared events while preserving provider, certificate-source, secret,
and acquisition-lock configuration.  Reset clears provider configuration,
sessions, acquisition locks, registered certificate sources, and their
canonical secure-storage secrets in scope.  The deleted certificate keyring
backend has no migration, fallback, or cleanup participation.  An explicit
provider reset leaves a differently configured provider untouched.  The broad
ambiguous `clear` operation ceases to exist.

Certificate secret set/remove has no backend option and always addresses the
selected profile's secure storage.  No certificate keyring selector,
registration, reconciliation prerequisite, or fallback remains.

`auth reset` and `config reset start/resume` are non-interactive destructive
operations and require explicit `--yes`; omission is a typed refusal.  Reset
status is read-only.  Start creates a new operation id and refuses when an
incomplete operation exists.  Status defaults to the sole active/latest
operation or accepts its id.  Resume defaults to the sole incomplete operation,
validates any supplied id, and rolls that exact journal forward; it never starts
a new reset.  A changed content fingerprint pauses resume and requires renewed
confirmation and retention approval.

Keep `switch`, `profile logout`, `ledger attach`, invoice `ledger link`, audit
`check`, `repair quarantine`, `repair reset-progress`, and the retained bulk
`reset` vocabulary.  Defer the lower-value `doclink` rename; its implementation
already composes the canonical attach path.

### Decision 4: migrate every contract surface atomically

For each hard change, update typed result payloads, JSON-schema path mappings,
locale declarations in all supported languages, help and risk metadata,
error-registry suggestions and `next_action` values, command-tree inventories,
MCP command mirrors, direct tests, Sphinx reference material, user guides, and
generated documentation sources.  Generated outputs are regenerated rather
than edited by hand.

Verification includes the real-behavior authority tests defined in the related
reference, live materialization proving unique leaf paths, documented-command
and JSON-schema conformance, locale coverage, clone audit, path-scoped quality
gates, formal code review, and attributable full-project gates.

Conformance also includes AST-based recurrence gates for new exact one-shot
SHA-256 bodies and duplicate local file-hash implementations, with explicit
allowance for the canonical helper and audited distinct cryptographic
primitives.  Namespace adoption validation must prove real consumer binding and
cannot pass on an empty or mismatched namespace inventory.  Duplication evidence
must be observed from the production tree before it contributes a GREEN health
result.

### Decision 5: make duplication evidence trustworthy

Make `dev.audit.duplication` the sole owner of the pinned jscpd invocation,
production source selection, output parsing, and typed result.  It passes the
production path in a platform-independent form, captures stdout and stderr,
preserves exit status and timeout information, and distinguishes observed zero,
observed clone clusters, unavailable execution, failed execution, and
unparseable output.

`dev.audit.report` consumes that typed result rather than constructing a second
jscpd command or interpreting missing output as zero.  Observed zero is GREEN;
observed clone debt is AMBER with its measured count; unavailable, failed,
timed-out, or unparseable evidence is AMBER and explicitly unavailable, never
false GREEN.  The clone-count policy remains advisory and separate from runner
health.

The `just` surface invokes the Python-owned runner directly rather than a shell
pipeline whose final parser process can mask jscpd failure.  All duplication
entry points therefore share one command definition, one parser, one status
taxonomy, and one production-tree scope.

## Rationale

The research establishes that this is not a naming-only problem.  Exact aliases
are cheap to remove, but the highest-risk findings are weaker parallel writers
that can strand pointers, retain live sessions, bypass retention and evidence
guards, or disconnect configured credentials from login.  Backend authority
must therefore precede surface simplification.

The selected verb set follows the accepted project rule and official common
CLI usage without normalizing for style alone.  `switch`, `attach`, `link`,
`check`, `repair`, and `reset` remain because they are established and accurate
in their retained scopes.  `lock`, `rekey`, `show-recovery`, and auth `clear`
change because they conflate materially different security states or effects.

Removing the fake replay and certificate keyring alternative is more honest and
less expensive than building substantial new subsystems merely to preserve
their current surface.  A future ADR may add real evidence replay or a typed
multi-backend certificate-secret model when those capabilities justify their
cost.

The active pre-release compatibility regime makes certificate-keyring deletion
both cheaper and more correct than reconciliation.  Migration would create code
and native-job obligations solely to preserve state that no released version
promised to retain, directly contradicting the repository's governing
compatibility decision.

The broader authority corrections follow the same principle as the CLI
simplification: one semantic policy owner, with transport-specific or
intent-specific wrappers preserved only where their contracts differ.
Centralizing namespace metadata, filed persistence, LLM review routing,
post-resolution registry projection, and export publication removes parallel
policy without flattening legitimate differences in authorization, failure
mode, legal intent, selection, or cryptographic semantics.

A false-green duplication report is an architecture defect in its own right.
Treating missing evidence as zero would allow future consolidation decisions to
rest on an unobserved tree.  A typed runner result makes the distinction between
“no clones were measured” and “no measurement occurred” enforceable.

## Consequences

- The project regains an operative import-architecture gate before feature work.
- Each audited state has one writer/policy owner, reducing the chance that a new
  command silently bypasses retention, session, credential, or evidence rules.
- The operator learns fewer commands, and security verbs describe the state
  transition they actually perform.
- Profile reset becomes more expensive to implement because it must preflight
  retention and coordinate several canonical services atomically.  That cost is
  required by the current safety defect.
- The hard cutover breaks every script or guide using removed spellings.  This
  is intentional pre-release policy; all repository-owned consumers move in the
  same campaign and no compatibility period exists.
- Evidence replay is temporarily unavailable rather than falsely advertised.
  Adding it later requires a distinct replay service and stored-input outcome
  tests.
- The unreleased certificate keyring backend and its migration obligations are
  deleted.  Named certificate secrets use selected-profile secure storage only.
  The independent master-key OS-keyring custody backend remains supported.
- Subject access remains a separate legally discoverable command but shares the
  complete portable-export transaction, category authority, handoff risk, and
  durable publication sequencing.  The sealed recovery archive remains
  separate.
- The documentation and conformance blast radius is large.  The plan must
  sequence backend authority, surface migration, documentation regeneration,
  and full validation so partially renamed states never ship.
- Storage namespace metadata has one enforceable registry authority; fixing
  drift may change incorrect diagnostic or catalogue metadata but requires no
  pre-release data migration.
- Filed capture retains distinct failure policies while removing duplicate
  latest-selection, ordering, persistence, and finalization logic.
- LLM review commands retain their different operator semantics while sharing
  typed application orchestration and truthful invocation provenance.
- Registry scoped and unscoped selection remain distinct, but equivalent report
  projections cannot drift.  The silently ignored unscoped `as_of` contract is
  removed or made effective.
- Eighteen one-shot digests and four further reducible bodies move to canonical
  hashing mechanics without merging streaming, keyed, certificate, checksum,
  or binary-digest operations.
- Duplication reporting can no longer claim GREEN without successfully observing
  the production tree.  Existing clone debt remains advisory but visible.
