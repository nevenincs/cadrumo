---
tags:
  - '#reference'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-research]]"
  - "[[2026-06-10-cli-operator-surface-adr]]"
---

# `cli-authority-verb-conformance` reference: `CLI authority and verb conformance source map`

This reference is the implementation-facing authority map for the CLI semantic
deduplication and cost-aware verb migration.  It records the inspected revision,
exact call graphs, owning services, safety constraints, blast radius, and
real-behavior verification targets.  It is intentionally explicit about false
positives so later implementation does not collapse operations that merely
share a low-level primitive.

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
one application profile-pointer transaction service backed only by core atomic
read/write/restore/clear primitives.  Repository and cold-start orchestration
delegate to it, preserving byte-exact failed-create rollback.

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

S25 adds interruption and exact-byte tests. S26 changes orchestration to use the
S24 pointer API and defines rollback concurrency policy. S27 changes
`ProfileRepository` to use the API. S28 changes profile health to use it. S29
tests repository concurrency, and S30 tests active-profile resolution. S24
doesn't reorder profile creation.

Atomic replacement isn't compare-and-swap. Until S26 defines rollback race
semantics, an unconditional restore can overwrite a concurrent selection.
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

### Authentication reset, sessions, and locks

Canonical graph:

```text
clear_operator_auth
  +--> delete_persisted_session
  +--> clear_auth_acquisition_lock
  +--> _apply_auth_clear_to_repository
       +--> AuthState()
       +--> provider/session/lock-cleared workflow events
```

Sources:

- `src/cadrumo/application/auth/_operator.py:640-778`
- `src/cadrumo/application/auth/_sessions.py:199-247`
- `src/cadrumo/application/auth/_acquisition_lock.py:82-157`

Competing `reset_config(AUTH|ALL)` at
`src/cadrumo/application/config_reset.py:189-194` only assigns `AuthState()` and
then reports `removed_auth_session=True`; it does not remove session objects,
locks, or emit canonical events.  The single owner is `clear_operator_auth`.
If ALL remains, auth cleanup must happen before deleting the active bucket.

Required real-behavior tests seed a real encrypted session, real acquisition
lock, and configured provider, then assert actual removals, post-state, and
events for both the dedicated auth surface and retained reset compositions.

### Certificate credential resolution

Current disconnected graph:

```text
certificate source select --> AuthState.certificate_path

certificate secret set/remove --> secure storage OR keyring
                                  [backend kind not persisted]

certificate check --> named-secret resolver --> default secure storage

auth login --> selected-path precondition --> unchanged Settings
                                      --> authenticator global path/secret
```

Sources:

- `src/cadrumo/application/auth/_certificate_sources_operator.py:250-293`
- `src/cadrumo/application/auth/_certificate_sources_operator.py:330-510`
- `src/cadrumo/application/auth/_certificate_secret_backend.py:85-316`
- `src/cadrumo/application/auth/_operator.py:550-611`
- `src/cadrumo/application/auth/_operator.py:781-805`
- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py:592-635`
- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py:1118-1141`

The target owner is an application `resolve_active_certificate_credentials`
service returning a typed scoped credential/settings bundle consumed by check,
status, test, and login.  Standardizing on secure storage is the lowest-cost
single authority.  If keyring remains, persist its backend kind per named
source and resolve it identically at every consumer.

Required real-behavior tests use a registered and selected certificate with a
real PKCS#12 payload and stored secret, without relying on global credential
settings; cover restart persistence, missing bound secret fail-closed behavior,
source removal/orphan reconciliation, and keyring only if retained.

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

`.importlinter:2` still declares `root_package = aeat`; the contracts below it
already name `cadrumo.*`.  `uv run lint-imports` therefore exits before building
the graph with `Could not find package 'aeat' in your Python path.`  Change the
root to `cadrumo`, execute the complete contract set without cache, and
reconcile every real boundary violation or stale ignore exposed by the restored
graph.  This is an implementation prerequisite, not an ambient warning.

The read-only corrected-root diagnostic analyzed 3,419 files and 16,149
dependencies.  After identifying two stale ignores, the complete five-contract
run reported three kept contracts and two broken contracts with three
root-cause paths:

- remove the stale `_censo -> adapters.**` and `_censo_sync -> adapters.**`
  entries;
- restore the exact
  `core.tests.test_isolation_fixture_state_root_coverage -> tests.secure_sql`
  shared-fixture route required by the accepted test-carveout ADR;
- remove `_irnr_income_ledger`'s unused default concrete construction and
  require the already injected `TransactionCatalogueRepositoryProtocol` in
  both the repository-loading function and the public IRNR resolver
  constructor, so no optional path can bypass the source mesh's one memoized
  transaction repository; and
- replace `_verification_actions`' type-only concrete invoice dependency with
  `InvoiceCatalogueRepositoryProtocol`, including the receiving OSS/IOSS
  resolver annotations, without adding an ignore.

The repair must not weaken contracts or add broad production exemptions.
Existing narrow real-adapter test exemptions and individually pinned
application construction edges remain governed by their accepted architecture
decisions; the dead IRNR fallback and type-only verification leak are removed,
not added to that debt ledger.

`src/cadrumo/tests/test_importlinter_ledger.py` is also stale: its regular
expression accepts only `aeat.*`, making all three count assertions vacuous.
Retarget it to `cadrumo`, narrow `diagnostics_run_health -> adapters.**` to
`adapters.outbound.llm`, and replace the obsolete 840/78/70 ceilings with the
post-reconciliation live counts 199/78/2.  Ceilings may decrease but may not be
raised.  Verification records all five contract results from an uncached run
and runs the repaired ledger test against non-empty parsed edges.

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
