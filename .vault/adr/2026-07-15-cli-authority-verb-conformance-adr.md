---
tags:
  - '#adr'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-research]]"
  - "[[2026-07-15-cli-authority-verb-conformance-reference]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr]]"
---

# `cli-authority-verb-conformance` adr: `Single backend authorities and cost-aware CLI verbs` | (**status:** `accepted`)

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

The audit also found that the import-linter gate cannot build its graph because
its configured root is the retired package `aeat`, and two exact SHA-256 bodies
remain outside the canonical core helper.  The operator explicitly brought the
degraded linter into scope; implementation cannot build on an inoperative
architecture gate.

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
- Secure-storage-only named certificate secrets are cheaper and easier to make
  authoritative than persisting and resolving a second per-source keyring
  backend.
- The repository is pre-release and forbids shims.  Documentation, locales,
  schemas, command mirrors, and tests move atomically with each hard change.
- The shared worktree contains unrelated active campaigns.  Implementation must
  preserve their changes and use path-scoped commits and gates.

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

### Option D: preserve every capability by implementing full replay and a
persisted per-source keyring selector in this campaign

Rejected for this campaign.  True replay is a substantial reproducibility
feature, and a second certificate-secret backend adds schema and resolution
complexity.  Removing the non-functional replay leaf and standardizing named
certificate secrets on secure storage reaches a coherent, smaller surface.

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
- Legacy keyring reconciliation is proven by required native integration jobs
  against Windows Credential Manager, macOS Keychain, and Linux Secret Service.
  Each platform job runs its real service test unconditionally and fails when
  the service is unavailable; no in-memory/test keyring, skip, or fallback
  backend is accepted as migration evidence.
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
3. migrate/reconcile named certificate secrets, then clear target-scoped auth
   sessions, locks, provider state, and secrets while each target is reachable;
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
check, auth status/test, and login.  Named certificate secrets use secure
storage only.  Before removing the keyring selector, run an idempotent
registered-source migration: if secure storage is empty and the deterministic
keyring entry exists, copy and verify it in secure storage before deleting the
keyring entry; if both exist and differ, refuse with a typed conflict and leave
both intact; if secure storage already matches, delete the keyring copy.  Every
keyring access/deletion failure is explicit and retryable.  Once reconciliation
completes, runtime credential resolution has no keyring fallback.

Route all purchase-evidence assignment through the attach policy.  Keep
`ledger link` for invoice relations and remove its evidence option.  If the
combined relation operation remains useful, implement it as one atomic
application transaction.

Move profile bundle export orchestration into one application service with a
typed purpose.  Portable export and subject access delegate to it; subject
access remains a separate legal-intent leaf.  Export uses a durable non-secret
operation record: write and fsync a restrictive-permission temporary artefact,
record `prepared` with target and digest, atomically replace the target, then
record/emit `completed`.  Resume reconciles a prepared operation by target
digest or removes an uncommitted temp file, so neither a false-success event nor
an invisible completed export is silently accepted.

Delegate the two residual SHA-256 implementations to `core.hashing.sha256_hex`.

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
sessions, acquisition locks, registered certificate sources, and both
reconciled secure-storage secrets and any deterministic legacy keyring entries
in scope.  An explicit provider reset leaves a differently configured provider
untouched.  The broad ambiguous `clear` operation ceases to exist.

Certificate secret set/remove has no backend option and always addresses the
selected profile's secure storage.  The one-time keyring reconciliation must
complete or fail explicitly before these new commands operate; no legacy
keyring-only registration is silently abandoned.

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
- Named certificate secrets lose the CLI-selectable keyring backend.  Secure
  storage becomes the single supported source until a future persisted backend
  model is approved.
- The subject-access command remains discoverable but shares export mechanics,
  preserving legal intent without duplicate serialization/event code.
- The documentation and conformance blast radius is large.  The plan must
  sequence backend authority, surface migration, documentation regeneration,
  and full validation so partially renamed states never ship.
