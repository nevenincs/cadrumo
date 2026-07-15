---
tags:
  - '#plan'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
tier: L3
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
---

<!-- RETIRED: S94, S95 -->

# `cli-authority-verb-conformance` plan

## Wave `W01` - Restore trustworthy architecture measurement

Repair the import graph and its count ratchets first; every later Wave depends on an uncached five-contract pass and a non-vacuous ledger inventory.

### Phase `W01.P01` - Repair the live import graph

Correct the package root, remove stale ledger entries, and eliminate the three exposed dependency paths without weakening a contract.

- [x] `W01.P01.S01` - Change the configured root package from aeat to cadrumo; `.importlinter`.
- [x] `W01.P01.S02` - Remove the stale live censo adapter ignore entry; `.importlinter`.
- [x] `W01.P01.S03` - Remove the stale user-profile censo-sync adapter ignore entry; `.importlinter`.
- [x] `W01.P01.S04` - Add only the exact core state-root test helper route to the reporting contract; `.importlinter`.
- [x] `W01.P01.S05` - Narrow diagnostics run-health adapter access to the outbound LLM package; `.importlinter`.
- [x] `W01.P01.S06` - Remove the concrete transaction-repository fallback and require TransactionCatalogueRepositoryProtocol; `src/cadrumo/application/aggregation/_irnr_income_ledger.py`.
- [x] `W01.P01.S07` - Require a non-optional TransactionCatalogueRepositoryProtocol in the public IRNR source resolver; `src/cadrumo/application/aggregation/_modelo_bindings.py`.
- [ ] `W01.P01.S08` - Exercise M210 aggregation through the real injected transaction repository; `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`.
- [x] `W01.P01.S09` - Replace verification's concrete invoice-repository boundary with InvoiceCatalogueRepositoryProtocol; `src/cadrumo/application/modelo/_verification_actions.py`.
- [ ] `W01.P01.S10` - Widen injected OSS and IOSS invoice-repository annotations while retaining the sole default composition path; `src/cadrumo/application/aggregation/_oss_ioss.py`.
- [ ] `W01.P01.S11` - Exercise dormant Modelo 369 verification through the real invoice repository Protocol boundary; `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`.

### Phase `W01.P02` - Repair the import-ledger ratchets

Make the ledger parser consume Cadrumo edges, narrow the remaining wildcard, and freeze the reconciled live ceilings.

- [ ] `W01.P02.S12` - Retarget the ignore-edge parser from aeat imports to cadrumo imports; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P02.S13` - Freeze the application-edge ceiling at 199; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P02.S14` - Freeze the application-source wildcard ceiling at 78; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P02.S15` - Freeze the domain test-edge ceiling at 2; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P02.S16` - Assert the parsed Cadrumo ignore inventory and layered-contract inventory are non-empty; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P02.S17` - Preserve the zero production-domain-to-adapters assertion and identify both test-only carveouts; `src/cadrumo/tests/test_importlinter_ledger.py`.

### Phase `W01.P03` - Prove the architecture prerequisite

Run focused boundary tests and an uncached complete import graph before any backend-authority work.

- [ ] `W01.P03.S18` - Run the repaired ignore-ledger tests and record the parsed 199, 78, and 2 inventory; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [ ] `W01.P03.S19` - Run the core state-root isolation test against real isolated secure storage; `src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py`.
- [ ] `W01.P03.S20` - Run the focused M210 IRNR real-storage suite after making both injection points required; `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`.
- [ ] `W01.P03.S21` - Run the focused Modelo 369 verification suite after widening the invoice boundary; `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`.
- [ ] `W01.P03.S22` - Run an uncached fresh-process import graph and require all five contracts with no unmatched ignore; `.importlinter`.
- [ ] `W01.P03.S23` - Block every later Wave unless all architecture prerequisite Steps are green; `.vault/exec/`.

## Wave `W02` - Consolidate profile, reset, auth, and certificate authorities

Establish the destructive and credential single-writer boundaries that the CLI hard cutover will expose; this Wave depends on Wave W01 and precedes every command migration.

### Phase `W02.P04` - Centralize active-profile pointer and logout

Create one atomic pointer boundary and make profile logout close every session, cache, lock, and pointer resource.

- [ ] `W02.P04.S24` - Add byte-exact pointer capture, atomic restore, and idempotent clear with restrictive temporary permissions and fsync; `src/cadrumo/core/_bucket_pointer_io.py`.
- [ ] `W02.P04.S25` - Prove exact pointer bytes and atomic write and clear behavior through real child-process interruption; `src/cadrumo/core/tests/test_bucket_pointer.py`.
- [ ] `W02.P04.S26` - Route every orchestration pointer write, clear, capture, restore, registration, and selection through the core pointer authority; `src/cadrumo/application/user_profile/_orchestration.py`.
- [ ] `W02.P04.S27` - Route repository pointer reads, selection, rollback, and deletion clear through the core pointer authority; `src/cadrumo/application/user_profile/_profile_repository.py`.
- [ ] `W02.P04.S28` - Route profile-health repair writes and clears through the core pointer authority; `src/cadrumo/application/workflow/_profile_health.py`.
- [ ] `W02.P04.S29` - Exercise repository rollback, repair, dangling-pointer, and concurrent pointer behavior against real files; `src/cadrumo/application/user_profile/tests/test_orchestration_pointer.py`.
- [ ] `W02.P04.S30` - Exercise active-profile resolution and repair through real lifecycle repositories; `src/cadrumo/application/workflow/tests/test_active_profile_resolution.py`.
- [ ] `W02.P04.S31` - Add idempotent active BucketSession close after key zeroization and engine disposal; `src/cadrumo/adapters/persistence/storage/master_key/_active_session.py`.
- [ ] `W02.P04.S32` - Add provider-session eviction that clears the OS-keystore cache and closes its BucketSession; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W02.P04.S33` - Prove repeated close zeroizes keys, seals the session, disposes engines, and removes active-session visibility; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session.py`.
- [ ] `W02.P04.S34` - Prove provider eviction closes real storage and permits a clean fresh reopen; `src/cadrumo/adapters/persistence/storage/tests/test_engine_session_lifecycle.py`.
- [ ] `W02.P04.S35` - Compose strong profile logout as session close, provider-cache eviction, lock release, and pointer clear; `src/cadrumo/application/user_profile/_orchestration.py`.
- [ ] `W02.P04.S36` - Prove strong logout releases a real lock, closes storage, clears the pointer, and remains idempotent; `src/cadrumo/application/user_profile/tests/test_orchestration.py`.

### Phase `W02.P06` - Split operator auth logout and reset

Separate session termination from destructive provider and credential reset while preserving scoped idempotency and events.

- [ ] `W02.P06.S37` - Replace AuthClearResult with typed AuthLogoutResult and AuthResetResult contracts; `src/cadrumo/application/auth/_operator_results.py`.
- [ ] `W02.P06.S38` - Re-export logout_operator_auth and reset_operator_auth while removing clear_operator_auth; `src/cadrumo/application/auth/__init__.py`.
- [ ] `W02.P06.S39` - Resolve operator scope for an explicit target bucket without switching the active pointer; `src/cadrumo/application/auth/_operator_scope.py`.
- [ ] `W02.P06.S40` - Delete only the requested target and provider session files without touching provider configuration; `src/cadrumo/application/auth/_sessions.py`.
- [ ] `W02.P06.S41` - Make acquisition-lock cleanup target and provider scoped and idempotent; `src/cadrumo/application/auth/_acquisition_lock.py`.
- [ ] `W02.P06.S42` - Implement session-only logout and destructive reset with distinct state and event semantics; `src/cadrumo/application/auth/_operator.py`.
- [ ] `W02.P06.S43` - Prove logout preserves provider and certificate-source configuration while clearing real sessions; `src/cadrumo/application/auth/tests/test_operator_storage_session.py`.
- [ ] `W02.P06.S44` - Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target; `src/cadrumo/application/auth/tests/test_operator.py`.
- [ ] `W02.P06.S45` - Prove provider and all-provider deletion leave unrelated bucket session files byte-identical; `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`.
- [ ] `W02.P06.S46` - Prove acquisition-lock cleanup is target scoped and repeatable with real lock files; `src/cadrumo/application/auth/tests/test_acquisition_lock.py`.

### Phase `W02.P07` - Unify active certificate credentials

Resolve selected certificate path and secret once, migrate legacy keyring entries safely, and feed check, status, test, and login from that bundle.

- [ ] `W02.P07.S47` - Replace selectable certificate-secret backends with secure storage and deterministic legacy-keyring reconciliation; `src/cadrumo/application/auth/_certificate_secret_backend.py`.
- [ ] `W02.P07.S48` - Add one active certificate credential resolver for source checks, secret mutation, registration removal, and reset cleanup; `src/cadrumo/application/auth/_certificate_sources_operator.py`.
- [ ] `W02.P07.S49` - Route auth status, test, and login certificate paths through the active credential resolver; `src/cadrumo/application/auth/_operator.py`.
- [ ] `W02.P07.S50` - Make the certificate authenticator consume the resolved typed credential bundle; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`.
- [ ] `W02.P07.S51` - Prove copy-verify-delete, equal-copy deletion, conflict refusal, retry, and secure-only resolution with real stores; `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`.
- [ ] `W02.P07.S52` - Prove register, select, check, status, test, and login consume the same resolved certificate bytes; `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`.
- [ ] `W02.P07.S53` - Run native Windows, macOS, and Linux keyring migration jobs against actual platform credential services; `.github/workflows/native-keyring-integration.yml`.

### Phase `W02.P05` - Build resumable all-profile reset

Replace scope reset with a durable target-scoped roll-forward operation composed from canonical deletion, auth, retention, and pointer services.

- [ ] `W02.P05.S54` - Add target deletion assessment and reset ownership fields to bucket-maintenance contracts; `src/cadrumo/application/bucket_maintenance/_contracts.py`.
- [ ] `W02.P05.S55` - Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion; `src/cadrumo/application/bucket_maintenance/_service.py`.
- [ ] `W02.P05.S56` - Define the authoritative deletion-relevant bucket fingerprint for assessment and resume; `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`.
- [ ] `W02.P05.S57` - Prove deletion assessment reports real retention blockers without mutating the bucket; `src/cadrumo/application/bucket_maintenance/tests/test_service_retention_floor.py`.
- [ ] `W02.P05.S58` - Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence; `src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py`.
- [ ] `W02.P05.S59` - Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models; `src/cadrumo/application/_config_reset_models.py`.
- [ ] `W02.P05.S60` - Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal; `src/cadrumo/application/_config_reset_repository.py`.
- [ ] `W02.P05.S61` - Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload; `src/cadrumo/application/tests/test_config_reset_repository.py`.
- [ ] `W02.P05.S62` - Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S63` - Acquire target locks in sorted UUID order and persist every retention decision before mutation; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S64` - Reconcile certificate secrets and invoke target-scoped auth reset before each target deletion; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S65` - Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S66` - Persist deleting ownership before deletion and completion after each irreversible transition; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S67` - Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status; `src/cadrumo/application/config_reset.py`.
- [ ] `W02.P05.S68` - Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults; `src/cadrumo/application/tests/test_config_reset.py`.
- [ ] `W02.P05.S69` - Prove every reset phase boundary resumes honestly in a fresh child process; `src/cadrumo/application/tests/test_config_reset_recovery.py`.
- [ ] `W02.P05.S70` - Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes; `src/cadrumo/application/tests/test_config_reset_concurrency.py`.

### Phase `W02.P21` - Harden passphrase and recovery custody

Expose explicit passphrase and recovery lifecycle operations while keeping mnemonic material off argv, output envelopes, and non-file custody backends.

- [ ] `W02.P21.S71` - Expose distinct recovery status, create, rotate, verify, and recover application operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [ ] `W02.P21.S72` - Make recovery create refuse an existing enrollment and rotate require an existing enrollment; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [ ] `W02.P21.S73` - Preserve the prior recovery envelope until a candidate mnemonic has been fully verified; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [ ] `W02.P21.S74` - Restrict recovery to file custody and return typed refusals for keyring and unsecured custody; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [ ] `W02.P21.S75` - Preserve the established recovery fingerprint across verification and recovery operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`.
- [ ] `W02.P21.S76` - Prove create refusal, rotate preconditions, candidate verification, and old-envelope survival with real encrypted files; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`.
- [ ] `W02.P21.S77` - Prove mnemonic verification and recovery never serialize secret material; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [ ] `W02.P21.S78` - Prove file-only custody and typed keyring or unsecured refusals across the custody matrix; `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`.
- [ ] `W02.P21.S79` - Prove passphrase change preserves encrypted data and survives failed candidate confirmation; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`.
- [ ] `W02.P21.S80` - Re-export only the explicit passphrase and recovery lifecycle operations; `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`.

## Wave `W03` - Consolidate remaining duplicated backend services

Remove evidence, export, hashing, and fake-replay duplication after the core profile and auth authorities are stable; the CLI Wave depends on these canonical services.

### Phase `W03.P08` - Enforce one ledger-evidence writer

Remove the generic evidence patch route and preserve invoice linking only through atomic application operations.

- [ ] `W03.P08.S81` - Make generic manual-field updates refuse purchase-evidence fields and reserve atomic catalogue and event writes for attach; `src/cadrumo/application/ledger/_actions_manual.py`.
- [ ] `W03.P08.S82` - Prove direct evidence patches fail and failed attach leaves catalogue and event history unchanged; `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`.
- [ ] `W03.P08.S83` - Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy; `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`.

### Phase `W03.P09` - Centralize profile export

Move portable and subject-access exports onto one crash-reconcilable application service with typed purpose.

- [ ] `W03.P09.S84` - Define typed portable and subject-access export purposes, requests, results, and schema-derived data categories; `src/cadrumo/application/user_profile/_bundle.py`.
- [ ] `W03.P09.S85` - Persist non-secret profile export operation states atomically outside the target artifact; `src/cadrumo/application/user_profile/_bundle_export_operation.py`.
- [ ] `W03.P09.S86` - Implement durable prepared and completed profile export with fsync, atomic replace, digest reconciliation, and resume; `src/cadrumo/application/user_profile/_bundle_export.py`.
- [ ] `W03.P09.S87` - Re-export the typed profile export service as the sole public export orchestration API; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `W03.P09.S88` - Prove portable and subject-access purposes share one schema-grounded bundle while retaining distinct purpose metadata; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [ ] `W03.P09.S89` - Prove each prepared, replace, and completed crash window resumes honestly in a fresh process; `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.

### Phase `W03.P10` - Remove residual hashing and replay duplication

Delegate both duplicate digest bodies to core and remove the check-shaped replay surface until real replay exists.

- [ ] `W03.P10.S90` - Delegate review-package recipient fingerprints to core sha256_hex; `src/cadrumo/application/modelo/_review_package_recipient_registry.py`.
- [ ] `W03.P10.S91` - Prove recipient fingerprints against known vectors and encrypted registry roundtrip; `src/cadrumo/application/modelo/tests/test_review_package_recipient_registry.py`.
- [ ] `W03.P10.S92` - Delegate MCP telemetry content digests to core sha256_hex; `src/cadrumo/entrypoints/mcp/_telemetry.py`.
- [ ] `W03.P10.S93` - Prove telemetry UTF-8 digests against known vectors and retained-record roundtrip; `src/cadrumo/entrypoints/mcp/tests/test_telemetry_retention.py`.

## Wave `W04` - Hard-cut over the operator CLI

Replace duplicate and misleading command doors with the accepted grammar without aliases; this Wave depends on the canonical backend services from Waves W02 and W03.

### Phase `W04.P11` - Cut over profile, sandbox, and reset commands

Remove lock and sandbox-use aliases and expose the accepted logout, switch, and reset start/status/resume grammar.

- [ ] `W04.P11.S96` - Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names; `src/cadrumo/entrypoints/cli/_config/_custody.py`.
- [ ] `W04.P11.S97` - Remove the config profile sandbox use registration and execution path without an alias; `src/cadrumo/entrypoints/cli/_config/_sandbox.py`.
- [ ] `W04.P11.S98` - Preserve config profile logout as the sole strong local-session logout command; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [ ] `W04.P11.S99` - Remove config lock and its weaker session-only execution path without an alias; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [ ] `W04.P11.S100` - Replace flat scoped reset registration with the config reset command group; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [ ] `W04.P11.S101` - Register only reset start, status, and resume with operation, retention, reason, and confirmation options; `src/cadrumo/entrypoints/cli/_config/_reset_cli.py`.
- [ ] `W04.P11.S102` - Prove exact sandbox labels work through switch while sandbox use and bare names are absent; `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`.
- [ ] `W04.P11.S103` - Prove switching and strong logout through real persisted custody state; `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`.
- [ ] `W04.P11.S104` - Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes; `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`.

### Phase `W04.P12` - Cut over passphrase and recovery commands

Replace rekey and overloaded recovery spellings with the accepted secure interactive and secrets-stdin lifecycle.

- [ ] `W04.P12.S105` - Replace config rekey with only config passphrase change and secure input handling; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `W04.P12.S106` - Replace recovery display and rotation spellings with recovery status, create, and rotate; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `W04.P12.S107` - Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `W04.P12.S108` - Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [ ] `W04.P12.S109` - Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths; `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.
- [ ] `W04.P12.S110` - Prove passphrase change through a real encrypted vault; `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`.
- [ ] `W04.P12.S111` - Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material; `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`.
- [ ] `W04.P12.S112` - Prove passphrases, mnemonics, and secret-input values are absent from help and examples; `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`.
- [ ] `W04.P12.S113` - Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution; `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`.
- [ ] `W04.P12.S114` - Align bootstrap and repair-policy inventories with the recovery family and flat recover exception; `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`.

### Phase `W04.P13` - Cut over auth and certificate commands

Expose distinct auth logout/reset and secure-storage-only certificate secret operations without clear or backend aliases.

- [ ] `W04.P13.S115` - Remove auth clear and register only login, logout, and destructive reset with mutually exclusive provider or all scope; `src/cadrumo/entrypoints/cli/_config/_auth.py`.
- [ ] `W04.P13.S116` - Remove certificate backend selection and key set and remove only by name through secure storage; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.
- [ ] `W04.P13.S117` - Prove provider and all logout and reset semantics plus reset confirmation; `src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py`.
- [ ] `W04.P13.S118` - Prove certificate secret set and remove against real secure storage and reject backend selection; `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`.
- [ ] `W04.P13.S119` - Require yes for auth reset and reset start and resume while keeping logout and status non-destructive; `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`.

### Phase `W04.P14` - Cut over ledger and audit commands

Remove ledger evidence bypass and fake replay while retaining canonical attach, invoice link, and audit check.

- [ ] `W04.P14.S120` - Restrict ledger link to invoice linkage and remove evidence-id and evidence-update result paths; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W04.P14.S121` - Remove modelo audit replay and retain only genuine audit check; `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`.
- [ ] `W04.P14.S122` - Prove attach remains distinct from invoice link and link rejects removed evidence grammar; `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`.
- [ ] `W04.P14.S123` - Prove modelo audit exposes check without replay or synthetic replay events; `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.
- [ ] `W04.P14.S124` - Assert the accepted root grammar exactly and reject every removed path and option; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

## Wave `W05` - Migrate contracts, locales, and documentation

Move every machine and human contract to the new grammar and regenerate owned outputs atomically after the live CLI has its final shape.

### Phase `W05.P15` - Migrate payload, token, and schema contracts

Update typed envelopes, operation mappings, write-policy tokens, and static command inventories to the hard-cutover paths.

- [ ] `W05.P15.S125` - Remove schema registrations for lock, rekey, legacy recovery, and sandbox-use commands; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `W05.P15.S126` - Define secret-free schemas for passphrase change, recovery status, create, rotate, verify, and flat recover; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `W05.P15.S127` - Replace auth clear with distinct auth logout and reset schemas and scope rules; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `W05.P15.S128` - Replace flat scoped reset with reset start, status, and resume schemas; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `W05.P15.S129` - Remove evidence-link input and evidence-update output fields from ledger link; `src/cadrumo/entrypoints/cli/_ledger_payloads.py`.
- [ ] `W05.P15.S130` - Remove modelo audit replay result schema and public command key; `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`.
- [ ] `W05.P15.S131` - Retire the modelo audit replayed event token after all consumers move to check results; `src/cadrumo/domain/buckets/_event.py`.
- [ ] `W05.P15.S132` - Update write-policy tokens for the accepted destructive and read-only command paths; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `W05.P15.S133` - Update the authoritative command manifest to the accepted paths and remove legacy keys; `src/cadrumo/application/operator_surface/_manifest.py`.
- [ ] `W05.P15.S134` - Update nested command-path token handling and examples for passphrase, recovery, auth, and reset groups; `src/cadrumo/entrypoints/cli/_errors.py`.
- [ ] `W05.P15.S135` - Replace the rekey recovery diagnostic with config passphrase change; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W05.P15.S136` - Replace verify-recovery terminology with config recovery verify in the recovery contract; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [ ] `W05.P15.S137` - Assert exact new schema keys, removed-key absence, exclusivity, and secret-free results; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [ ] `W05.P15.S138` - Update root fallback write classification without accepting removed command paths; `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`.

### Phase `W05.P16` - Migrate locales and operator metadata

Move all four locale catalogues plus help, risk, error, and MCP mirrors to the accepted grammar.

- [ ] `W05.P16.S139` - Replace removed command, option, help, risk, and error nodes with accepted English grammar; `src/cadrumo/locales/en.yml`.
- [ ] `W05.P16.S140` - Replace removed command, option, help, risk, and error nodes with accepted Spanish grammar; `src/cadrumo/locales/es.yml`.
- [ ] `W05.P16.S141` - Replace removed command, option, help, risk, and error nodes with accepted Catalan grammar; `src/cadrumo/locales/ca.yml`.
- [ ] `W05.P16.S142` - Replace removed command, option, help, risk, and error nodes with accepted Hungarian grammar; `src/cadrumo/locales/hu.yml`.
- [ ] `W05.P16.S143` - Reconcile intentional identical-locale declarations after the grammar migration; `src/cadrumo/locales/_intentional_identical.json`.
- [ ] `W05.P16.S144` - Require four-locale parity and reject orphaned locale nodes for removed grammar; `src/cadrumo/locales/tests/test_audit.py`.
- [ ] `W05.P16.S145` - Classify passphrase, recovery, auth reset, and reset start and resume under exact new risk keys; `src/cadrumo/application/operator_surface/_risk_table.py`.
- [ ] `W05.P16.S146` - Replace stale help records with accepted profile, recovery, auth, certificate, reset, ledger, and audit descriptions; `src/cadrumo/application/operator_surface/_help.py`.
- [ ] `W05.P16.S147` - Update operator-surface contract notes to the accepted grammar and authority semantics; `src/cadrumo/application/operator_surface/_contract.py`.
- [ ] `W05.P16.S148` - Replace flat reset and legacy custody next actions with registered accepted commands; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [ ] `W05.P16.S149` - Assert operator help, risk, mutability, schema, and live-registration inventories remain exact mirrors; `src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py`.
- [ ] `W05.P16.S150` - Prove suggestions resolve only to accepted registered commands; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
- [ ] `W05.P16.S151` - Reject removed command strings in diagnostics, help, errors, and schema metadata; `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
- [ ] `W05.P16.S152` - Replace sandbox-use identity gating with canonical config switch handling; `src/cadrumo/entrypoints/mcp/_identity_gate.py`.
- [ ] `W05.P16.S153` - Derive exact nested passphrase, recovery, auth, reset, ledger, and audit inputs from accepted schemas; `src/cadrumo/entrypoints/mcp/_input_schema.py`.
- [ ] `W05.P16.S154` - Remove legacy MCP tool keys and dispatch only accepted CLI mirrors; `src/cadrumo/entrypoints/mcp/_tools.py`.
- [ ] `W05.P16.S155` - Assert MCP descriptors and dispatch mirror accepted keys and reject removed keys; `src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`.
- [ ] `W05.P16.S156` - Assert MCP risk annotations match the operator risk table; `src/cadrumo/entrypoints/mcp/tests/test_risk_table_parity.py`.
- [ ] `W05.P16.S157` - Assert MCP mutability distinguishes read-only status from destructive operations; `src/cadrumo/entrypoints/mcp/tests/test_write_policy_mutability_parity.py`.
- [ ] `W05.P16.S158` - Prove canonical switch identity gating and removed sandbox-use unavailability; `src/cadrumo/entrypoints/mcp/tests/test_identity_gate.py`.
- [ ] `W05.P16.S159` - Prove generated MCP input schemas for every accepted changed command; `src/cadrumo/entrypoints/mcp/tests/test_input_schema.py`.
- [ ] `W05.P16.S160` - Refresh command-search expectations only for accepted keys and reject removed tokens; `src/cadrumo/application/command_search/tests/test_command_ranking_golden.py`.

### Phase `W05.P17` - Rewrite and regenerate user documentation

Use the mandatory structured documentation workflow to update guides and references, then regenerate CLI-owned documentation outputs.

- [ ] `W05.P17.S161` - Invoke the mandatory vaultspec-documentation workflow and keep its render-and-verify gate active for this Phase; `docs/`.
- [ ] `W05.P17.S162` - Rewrite data-access protection procedures for passphrase, recovery, logout, quarantine, and reset; `docs/how-to/protect-data-access.md`.
- [ ] `W05.P17.S163` - Rewrite authentication procedures for login, logout, reset, and backend-free certificate secrets; `docs/how-to/authenticate-with-aeat.md`.
- [ ] `W05.P17.S164` - Rewrite profile setup and navigation for exact switch labels and strong logout; `docs/how-to/profile-setup.md`.
- [ ] `W05.P17.S165` - Rewrite ledger evidence guidance to separate attach from invoice-only link; `docs/how-to/ledger-evidence.md`.
- [ ] `W05.P17.S166` - Rewrite bank-import examples to separate evidence attach from invoice link; `docs/how-to/import-bank-statements.md`.
- [ ] `W05.P17.S167` - Align the how-to index with logout, passphrase, recovery, and reset lifecycle terminology; `docs/how-to/index.md`.
- [ ] `W05.P17.S168` - Align the command and configuration overview with the accepted hierarchy and security semantics; `docs/reference/commands-and-configuration.md`.
- [ ] `W05.P17.S169` - Regenerate data-access sequence goldens from real accepted commands; `docs/_sequences/how-to/protect-data-access/`.
- [ ] `W05.P17.S170` - Regenerate authentication sequence goldens for login, logout, reset, and certificate secrets; `docs/_sequences/how-to/authenticate-with-aeat/`.
- [ ] `W05.P17.S171` - Regenerate bank-import sequence goldens for attach and invoice link; `docs/_sequences/how-to/import-bank-statements/`.
- [ ] `W05.P17.S172` - Regenerate CLI reference pages from the live command tree and prove removed pages are absent; `dev/docs/tests/test_cli_reference_conformance.py`.
- [ ] `W05.P17.S173` - Regenerate the static CLI tree from the live command tree and verify exact accepted paths; `dev/docs/tests/test_cli_tree.py`.
- [ ] `W05.P17.S174` - Regenerate terminology coverage from authoritative sources and reject removed command tokens; `src/cadrumo/_data/terminology/evaluation/coverage-report.json`.
- [ ] `W05.P17.S175` - Validate every regenerated sequence against its directive and command contract; `dev/docs/tests/test_sequence_contract.py`.
- [ ] `W05.P17.S176` - Build Sphinx with warnings as errors and verify references, tree, links, and sequences; `dev/docs/tests/test_docs_build.py`.

## Wave `W06` - Prove conformance and close the campaign

Run focused real-behavior evidence, whole-surface conformance, duplication re-audit, formal review, and requirement-by-requirement closure after all prior Waves land.

### Phase `W06.P18` - Run focused real-behavior verification

Exercise every canonical authority with real encrypted storage, processes, locks, certificate services, and CLI invocation.

- [ ] `W06.P18.S177` - Run focused pointer, switch, logout, reset, and bootstrap-policy suites against real persisted state; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W06.P18.S178` - Run passphrase and recovery lifecycle suites against real encrypted vaults and secure input channels; `src/cadrumo/entrypoints/cli/_config/tests/`.
- [ ] `W06.P18.S179` - Run auth and certificate suites against real storage and provider boundaries; `src/cadrumo/application/auth/tests/`.
- [ ] `W06.P18.S180` - Run ledger attach and invoice-link suites and prove the generic evidence bypass cannot execute; `src/cadrumo/application/ledger/tests/`.
- [ ] `W06.P18.S181` - Run profile export crash-window suites across real fresh processes; `src/cadrumo/application/user_profile/tests/`.
- [ ] `W06.P18.S182` - Run modelo audit check suites and prove synthetic replay cannot execute; `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.
- [ ] `W06.P18.S183` - Run MCP dispatch, identity, input-schema, risk, mutability, and telemetry parity suites; `src/cadrumo/entrypoints/mcp/tests/`.
- [ ] `W06.P18.S184` - Run every native credential migration job without fake backends, skips, or fallbacks; `.github/workflows/native-keyring-integration.yml`.

### Phase `W06.P19` - Run whole-surface conformance and duplication audits

Materialize the CLI, prove schema, locale, docs, and MCP agreement, rerun clone and semantic duplication checks, and execute attributable quality gates.

- [ ] `W06.P19.S185` - Materialize the complete lazy CLI tree in a fresh process and assert every leaf path is unique; `src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`.
- [ ] `W06.P19.S186` - Compare the materialized tree with the accepted additions and removals and fail on unplanned leaf loss; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.
- [ ] `W06.P19.S187` - Run documented-command path and argument conformance against the live tree; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `W06.P19.S188` - Run JSON schema registration and output conformance for every live leaf; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [ ] `W06.P19.S189` - Run self-referential CLI string conformance and reject every removed spelling; `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
- [ ] `W06.P19.S190` - Run suggestion and next-action conformance against the live tree; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
- [ ] `W06.P19.S191` - Run four-locale catalogue and rendered-help coverage for every changed path; `src/cadrumo/locales/tests/`.
- [ ] `W06.P19.S192` - Run generated CLI reference and static-tree conformance; `dev/docs/tests/`.
- [ ] `W06.P19.S193` - Run the mandatory documentation render-and-verify workflow after final command materialization; `docs/`.
- [ ] `W06.P19.S194` - Run a fresh uncached import graph and require all five contracts; `.importlinter`.
- [ ] `W06.P19.S195` - Run Ruff against every feature-owned Python file; `src/cadrumo/`.
- [ ] `W06.P19.S196` - Run the complete feature-owned real-behavior test inventory; `src/cadrumo/`.
- [ ] `W06.P19.S197` - Run the feature-surface-gate skill against only feature-owned paths; `.`.
- [ ] `W06.P19.S198` - Run repository ratchets for skips, test doubles, monkeypatching, tautology, markers, and discovery drift; `src/cadrumo/tests/`.
- [ ] `W06.P19.S199` - Run full collect-only and classify every collection failure by owner; `src/cadrumo/`.
- [ ] `W06.P19.S200` - Run the complete unit suite and record the attributable result; `src/cadrumo/`.
- [ ] `W06.P19.S201` - Run the complete serial integration suite and record the attributable result; `src/cadrumo/`.
- [ ] `W06.P19.S202` - Run the complete documentation build and conformance gate; `docs/`.
- [ ] `W06.P19.S203` - Run the duplication audit and compare clone clusters and duplicated-line percentage with the research baseline; `src/cadrumo/`.
- [ ] `W06.P19.S204` - Dispatch a fresh Luna xhigh agent swarm over every audited functionality cluster; `src/cadrumo/`.
- [ ] `W06.P19.S205` - Rerun Vaultspec-RAG semantic searches for duplicate declarations, dormant compatibility routes, and parallel writers; `src/cadrumo/`.
- [ ] `W06.P19.S206` - Confirm every semantic candidate with targeted symbol and call-site searches before classification; `src/cadrumo/`.
- [ ] `W06.P19.S207` - Record canonical owner, surviving consumers, and disposition for every functionality cluster; `.vault/audit/`.
- [ ] `W06.P19.S208` - Record unrelated concurrent failures separately without claiming global green; `.vault/exec/`.

### Phase `W06.P20` - Perform formal review and completion audit

Run the formal code-review skill, reconcile findings, and prove every accepted ADR requirement before declaring completion.

- [ ] `W06.P20.S209` - Invoke vaultspec-code-review over the complete feature diff for safety, intent, boundary direction, and test quality; `.`.
- [ ] `W06.P20.S210` - Resolve every in-scope blocker or major finding through its owning implementation Step; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S211` - Rerun every focused or full gate invalidated by a corrective edit; `.vault/exec/`.
- [ ] `W06.P20.S212` - Record a zero-blocker and zero-major formal review verdict; `.vault/audit/`.
- [ ] `W06.P20.S213` - Confirm every closed implementation Step has an attributable execution record; `.vault/exec/`.
- [ ] `W06.P20.S214` - Confirm no removed CLI spelling survives in source, locales, tests, docs, schemas, MCP, or suggestions; `.`.
- [ ] `W06.P20.S215` - Confirm every accepted backend authority has one canonical writer and no bypass path; `src/cadrumo/`.
- [ ] `W06.P20.S216` - Audit every accepted ADR requirement against code and objective verification evidence; `.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md`.
- [ ] `W06.P20.S217` - Rebuild the feature index after all plan, execution, audit, ADR, research, and reference artifacts are final; `.vault/`.
- [ ] `W06.P20.S218` - Run the plan structural check and refuse closure while any Step remains open or malformed; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S219` - Run feature-scoped Vaultspec checks and resolve every attributable finding; `.vault/`.
- [ ] `W06.P20.S220` - Run repository-wide Vaultspec checks and triage unrelated residuals honestly; `.vault/`.
- [ ] `W06.P20.S221` - Run the required fresh-context campaign-close honesty review; `.vault/audit/`.
- [ ] `W06.P20.S222` - Mark the plan complete only after every Step, record, gate, blocker, and major finding is closed; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.

## Description

Execute the accepted decisions in `2026-07-15-cli-authority-verb-conformance-adr.md`, grounded by `2026-07-15-cli-authority-verb-conformance-research.md` and `2026-07-15-cli-authority-verb-conformance-reference.md`. The campaign first repairs the false-green import-linter graph, then removes duplicated backend authorities, and only then hard-cuts the small approved set of misleading or duplicate CLI doors. The cutover includes every machine and human contract and introduces no aliases, hidden registrations, compatibility parsers, fake replay behavior, or parallel write paths.

The work deliberately does not rename the broader 282-leaf CLI for style alone. Each accepted rename closes a duplicate or materially misleading authority: lock becomes strong profile logout, sandbox use collapses into switch, ambiguous reset becomes a resumable all-profile reset lifecycle, rekey and recovery commands become explicit custody operations, auth clear splits into logout and reset, ledger link becomes invoice-only, and audit replay is removed until genuine replay exists.

## Steps

## Parallelization

- Waves execute in order. Wave W01 is a hard prerequisite: no backend or CLI work begins until the focused tests and the fresh uncached five-contract import graph are green.
- Within Wave W01, the IRNR and invoice boundary repairs may proceed in parallel with the ratchet test repair, but `.importlinter` has one owner and the final `199/78/2` proof runs only after every boundary change lands.
- Within Wave W02, pointer and logout work lands before auth and reset composition. Auth and certificate Phases may proceed in parallel on disjoint files. Reset repository and maintenance contracts may be prepared in parallel, but reset orchestration waits for pointer, logout, auth, and certificate authorities.
- Within Wave W03, ledger evidence, profile export, and SHA-256 delegation may run in parallel because they have disjoint owners. Each Phase lands with its real-behavior tests.
- Waves W04 and W05 form one indivisible hard-cutover batch. There is no merge, release, or compatibility checkpoint between command removal and schema, locale, MCP, test, and documentation migration.
- Locale files have distinct owners and may be updated in parallel. Generated documentation is regenerated only after the live command tree, schemas, locales, and MCP surface are final.
- No two agents edit the same source, test, locale, generated output, documentation file, or Vault artifact concurrently. Existing peer changes, including changes in `_calculation_actions.py`, are preserved; no stash, reset, checkout, or unrelated cleanup is permitted.
- Wave W06 begins after code and documentation freeze. Read-only conformance, duplication, and static checks may run in parallel, while unit and integration lanes retain their prescribed isolation. Any corrective edit reopens its owning Step and invalidates dependent evidence.

## Verification

- A fresh `lint-imports --no-cache` process keeps all five contracts, reports no unmatched ignore, and the non-vacuous ledger ratchet freezes `199` application edges, `78` application-source wildcards, and `2` test-only domain edges.
- Targeted real-behavior suites prove one atomic pointer writer, strong logout, target-scoped auth logout/reset, secure certificate migration, durable all-profile reset, one ledger-evidence writer, crash-reconcilable export, and canonical hashing.
- Native Windows, macOS, and Linux credential-store jobs pass without fakes, mocks, patches, fallback backends, skips, or xfail.
- The materialized CLI tree equals the accepted grammar exactly and contains no duplicate path, old alias, hidden registration, compatibility parser, removed option, or unplanned leaf loss.
- Payload schemas, write policy, risk/help metadata, error suggestions, all four locales, MCP mirrors, authored documentation, generated references, static CLI tree, and sequence artifacts agree with the live command tree.
- Passphrases, recovery mnemonics, and secret-input values never appear in argv, result envelopes, logs, help, examples, or generated documentation.
- Focused Ruff, pytest, documentation, feature-surface, Vaultspec, uncached import-linter, full collection, unit, integration, and duplication gates have attributable recorded outcomes.
- A fresh Luna xhigh swarm and Vaultspec-RAG semantic audit find no second declaration, dormant compatibility route, or parallel writer in any audited functionality cluster; every candidate has a recorded canonical owner and disposition.
- Formal `vaultspec-code-review` reports zero blocker and zero major findings, the fresh-context honesty review passes, every accepted ADR requirement has objective evidence, and every Step has an execution record before the plan is marked complete.
