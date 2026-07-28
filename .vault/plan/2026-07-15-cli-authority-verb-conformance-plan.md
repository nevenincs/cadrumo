---
tags:
  - '#plan'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-28'
tier: L3
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: S38, S39, S40, S41, S42, S53, S94, S95, S115, S117, S127, S184 -->

# `cli-authority-verb-conformance` plan

## Status: resumed, and this document is the live tracking surface

This plan was rescoped and split on 2026-07-17 into six smaller, individually-closeable successor plans, and was marked SUPERSEDED at 64 of 254 steps. Both halves of that disposition have since been overtaken and the header is corrected here rather than left standing, because a reader who trusts it will work the wrong document.

All six successors are complete: `2026-07-17-duplication-evidence-repair-plan` (7 of 7), `2026-07-17-auth-cert-recovery-custody-plan` (56 of 56), `2026-07-17-all-profile-reset-plan` (32 of 32), `2026-07-17-ledger-evidence-atomicity-plan` (23 of 23), `2026-07-17-export-publication-plan` (19 of 19), and `2026-07-17-cli-authority-quality-backlog-plan` (27 of 27). The work they carried is done, so the "work its successors" instruction now points at six closed documents.

Execution resumed against THIS plan afterwards, which is why its own count has moved from the 64 the header quoted to a materially higher figure, and why the campaign-close honesty review of 2026-07-25 enumerates this document's open Steps as the campaign's remaining surface. Waves W01 through W04 are complete and evidenced; W05 and W06 carry the remainder.

The instruction that stands: work this plan, and verify each open W05 Step against its NAMED SURFACE before checking it rather than inferring satisfaction from the live command tree. The close review established why - the single W05 Step it actually checked against its surface was the one genuinely undone, and it was concealing a fail-open in the profile-bound write guard.

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
- [x] `W01.P01.S08` - Exercise M210 aggregation through the real injected transaction repository; `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`.
- [x] `W01.P01.S09` - Replace verification's concrete invoice-repository boundary with InvoiceCatalogueRepositoryProtocol; `src/cadrumo/application/modelo/_verification_actions.py`.
- [x] `W01.P01.S10` - Widen injected OSS and IOSS invoice-repository annotations while retaining the sole default composition path; `src/cadrumo/application/aggregation/_oss_ioss.py`.
- [x] `W01.P01.S11` - Exercise dormant Modelo 369 verification through the real invoice repository Protocol boundary; `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`.

### Phase `W01.P02` - Repair the import-ledger ratchets

Make the ledger parser consume Cadrumo edges, narrow the remaining wildcard, and freeze the reconciled live ceilings.

- [x] `W01.P02.S12` - Retarget the ignore-edge parser from aeat imports to cadrumo imports; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P02.S13` - Freeze the application-edge ceiling at 199; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P02.S14` - Freeze the application-source wildcard ceiling at 78; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P02.S15` - Freeze the domain test-edge ceiling at 2; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P02.S16` - Assert the parsed Cadrumo ignore inventory and layered-contract inventory are non-empty; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P02.S17` - Preserve the zero production-domain-to-adapters assertion and identify both test-only carveouts; `src/cadrumo/tests/test_importlinter_ledger.py`.

### Phase `W01.P03` - Prove the architecture prerequisite

Run focused boundary tests and an uncached complete import graph before any backend-authority work.

- [x] `W01.P03.S18` - Run the repaired ignore-ledger tests and record the parsed 199, 78, and 2 inventory; `src/cadrumo/tests/test_importlinter_ledger.py`.
- [x] `W01.P03.S19` - Run the core state-root isolation test against real isolated secure storage; `src/cadrumo/core/tests/test_isolation_fixture_state_root_coverage.py`.
- [x] `W01.P03.S20` - Run the focused M210 IRNR real-storage suite after making both injection points required; `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`.
- [x] `W01.P03.S21` - Run the focused Modelo 369 verification suite after widening the invoice boundary; `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`.
- [x] `W01.P03.S22` - Run an uncached fresh-process import graph and require all five contracts with no unmatched ignore; `.importlinter`.
- [x] `W01.P03.S23` - Block every later Wave unless all architecture prerequisite Steps are green; `.vault/exec/`.

## Wave `W02` - Consolidate profile, reset, auth, and certificate authorities

Establish the destructive and credential single-writer boundaries that the CLI hard cutover will expose; this Wave depends on Wave W01 and precedes every command migration.

### Phase `W02.P04` - Centralize active-profile pointer and logout

Create one atomic pointer boundary and make profile logout close every session, cache, lock, and pointer resource.

- [x] `W02.P04.S24` - Add byte-exact pointer capture, atomic restore, idempotent clear with restrictive temporary permissions and fsync, complete short writes in the hardened byte writer, prove complete writes against a real operating-system descriptor, delegate master-key secure writes to the canonical hardened writer, remove the duplicated sensitive-persistence exemption, and expose the core pointer API; `src/cadrumo/core/_bucket_pointer_io.py, src/cadrumo/core/atomic_write.py, src/cadrumo/core/__init__.py, src/cadrumo/core/tests/test_atomic_write.py, src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py, src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [x] `W02.P04.S25` - Prove exact pointer bytes and atomic write and clear behavior through real child-process interruption; `src/cadrumo/core/tests/test_bucket_pointer.py`.
- [x] `W02.P04.S26` - Introduce one neutral reentrant active-profile pointer transaction service, retire the duplicate storage-adapter lock export, and route orchestration write, clear, capture, rollback, registration, and selection through the core-owned authority under a continuous whole-create-span lock with bounded fail-closed contention; `src/cadrumo/application/user_profile/_profile_pointer_transaction.py, src/cadrumo/application/user_profile/_orchestration.py, src/cadrumo/application/user_profile/__init__.py, src/cadrumo/core/__init__.py, src/cadrumo/adapters/persistence/storage/__init__.py, src/cadrumo/adapters/persistence/storage/tests/test_substrate_smoke.py, src/cadrumo/adapters/persistence/storage/tests/test_rotation.py, src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py, dev/import_hygiene_test_debt.json, src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [x] `W02.P04.S27` - Route repository pointer reads, selection, rollback, and deletion clear through the same reentrant active-profile pointer transaction, preserve whole-create-span ownership and pointer-first test lock order, and remove the retired text-rollback persistence exemption; `src/cadrumo/application/user_profile/_profile_repository.py, src/cadrumo/application/user_profile/tests/test_profile_repository.py, src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.
- [x] `W02.P04.S28` - Route profile-health repair mutation through the shared reentrant active-profile pointer transaction with locked reassessment, bounded fail-closed contention, and the health result's repairable flag as the sole eligibility authority, correct the three lifecycle CLI integration pointer setup calls to use the isolated backend root, then prove pointer-sourced unreadable-manifest repair, cold no-op behavior, and real CLI pointer repair, absence, and dangling-pointer outcomes; `src/cadrumo/application/workflow/_profile_health.py, src/cadrumo/application/workflow/tests/test_profile_health.py, src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`.
- [x] `W02.P04.S29` - Prove byte-exact failed-create rollback through the repository transaction nested under outer pointer ownership, then prove dangling-pointer repair fails closed under real thread contention and succeeds after lock release against real files; `src/cadrumo/application/user_profile/tests/test_orchestration_pointer.py`.
- [x] `W02.P04.S30` - Canonicalize active-profile labels to immutable bucket UUIDs at the WorkflowState and profile-health boundaries by composing the core precedence resolver with the existing manifest resolver without adding resolver authority, then prove a real lifecycle-repository-backed label override resolves its encrypted record and keeps a lower-priority dangling pointer ineligible until the override is cleared, after which the pointer becomes authoritative and repairable; `src/cadrumo/application/workflow/_models.py, src/cadrumo/application/workflow/_profile_health.py, src/cadrumo/application/workflow/tests/test_active_profile_resolution.py`.
- [x] `W02.P04.S31` - Introduce one public idempotent active-session eviction boundary that closes the currently bound BucketSession before clearing ContextVar visibility, route idle-expiry and interpreter-exit cleanup through it, and re-export it through the master-key and storage facades; `src/cadrumo/adapters/persistence/storage/master_key/_active_session.py, src/cadrumo/adapters/persistence/storage/master_key/__init__.py, src/cadrumo/adapters/persistence/storage/__init__.py`.
- [x] `W02.P04.S32` - Centralize provider teardown in the shared exit boundary so production and ephemeral providers atomically detach their bookkeeping, close only their exact owned BucketSession before unwinding activation, reuse that boundary after failed entry, and do not recreate the retired OS-keyring cache; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py, src/cadrumo/adapters/persistence/storage/master_key/_master_key_ephemeral.py`.
- [x] `W02.P04.S33` - Prove repeated active-session eviction removes current and boolean ContextVar visibility after the existing key zeroization and engine disposal, preserves nested outer-session restoration, and clears an already sealed binding; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session.py`.
- [x] `W02.P04.S34` - Prove same-object file-provider eviction closes real bucket-routed storage, clears provider and active-session bookkeeping, and permits a clean fresh reopen with the persisted bucket DEK and distinct session and engine handles; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`.
- [x] `W02.P04.S35` - Compose strong profile logout by closing and evicting the current BucketSession before clearing the active pointer under the existing pointer transaction, then let provider bookkeeping unwind through its owning context and release the pointer sidecar lock without inventing a provider cache or bucket-lock authority; `src/cadrumo/application/user_profile/_orchestration.py`.
- [x] `W02.P04.S36` - Refuse logout under an explicit profile override, prove pointer-sourced strong logout honors lock contention and closes real storage idempotently, and restore single declaration authority to the error registry; `src/cadrumo/application/user_profile/{__init__.py,_orchestration.py,tests/test_orchestration.py}; src/cadrumo/entrypoints/cli/_bootstrap_exempt.py; src/cadrumo/core/errors/{_registry.py,registry/_application_part1.py,registry/_application_part2.py,registry/_adapters_part2.py,registry/_domain_part2.py,registry/_entrypoints.py,tests/test_registry.py,tests/test_registry_enforcement.py}`.

### Phase `W02.P06` - Split operator auth logout and reset

Separate session termination from destructive provider and credential reset while preserving scoped idempotency and events.

- [x] `W02.P06.S37` - Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract/risk/help/write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper; `src/cadrumo/application/auth/_operator_results.py; src/cadrumo/application/auth/_operator_scope.py; src/cadrumo/application/auth/_sessions.py; src/cadrumo/application/auth/_acquisition_lock.py; src/cadrumo/application/auth/_operator.py; src/cadrumo/application/auth/__init__.py; src/cadrumo/application/tests/test_cli_workflow_verification.py; src/cadrumo/application/auth/tests/test_operator_storage_session.py; src/cadrumo/entrypoints/cli/_config/_auth.py; src/cadrumo/entrypoints/cli/_config_payloads.py; src/cadrumo/application/storage_write_policy.py; src/cadrumo/application/operator_surface/_contract.py; src/cadrumo/application/operator_surface/_risk_table.py; src/cadrumo/application/operator_surface/_help.py; src/cadrumo/core/errors/registry/_application_part1.py; src/cadrumo/locales/en.yml; src/cadrumo/locales/es.yml; src/cadrumo/locales/ca.yml; src/cadrumo/locales/hu.yml; src/cadrumo/entrypoints/cli/_config/tests/test_auth_round5_surface.py; src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py; src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py; src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`.
- [x] `W02.P06.S43` - Prove logout preserves provider and certificate-source configuration while clearing real sessions; `src/cadrumo/application/auth/tests/test_operator_storage_session.py`.
- [x] `W02.P06.S44` - Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target; `src/cadrumo/application/auth/tests/test_operator.py`.
- [x] `W02.P06.S45` - Prove provider and all-provider deletion leave unrelated bucket session files byte-identical; `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`.
- [x] `W02.P06.S46` - Prove acquisition-lock cleanup is target scoped and repeatable with real lock files; `src/cadrumo/application/auth/tests/test_acquisition_lock.py`.

### Phase `W02.P07` - Unify active certificate credentials

Resolve the selected certificate path and secure-storage secret once, delete the unreleased certificate keyring alternative, and feed check, status, test, and login from one typed bundle.

- [x] `W02.P07.S47` - Delete the certificate keyring backend, backend-kind selector, factory branch, exports, and certificate-specific keyring service and account code while retaining secure storage as the only certificate-secret backend and preserving independent master-key OS-keyring custody; `src/cadrumo/application/auth/_certificate_secret_backend.py; src/cadrumo/application/auth/__init__.py`.
- [x] `W02.P07.S48` - Make the active certificate credential resolver and named-source certificate check use only selected-profile secure storage with explicit fail-closed absence, and make ordinary certificate-secret set/remove crash-resumable through one secret-free durable intent or outbox carrying a stable operation id, event kind and timestamp, prior-presence state, and non-secret completion witness, resuming pending mutations before accepting a new mutation without migration, fallback, probing, reconciliation, or a parallel secret writer; `src/cadrumo/application/auth/_certificate_sources_operator.py; src/cadrumo/application/auth/_certificate_secret_backend.py; src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py; src/cadrumo/application/auth/tests/test_certificate_sources_check.py`.
- [x] `W02.P07.S49` - Route auth status, test, login, central session acquisition, live callers, state projection, and modelo provider construction through the active certificate credential resolver by centralizing exact certificate credential projection in the application provider factory and transporting explicit absent values without changing omitted-provider reporting semantics; `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py; src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py; src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py; src/cadrumo/adapters/persistence/storage/master_key/_master_key.py; src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py; src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session.py; src/cadrumo/tests/secure_sql.py; src/cadrumo/application/auth/__init__.py; src/cadrumo/application/auth/_certificate_secret_backend.py; src/cadrumo/application/auth/_certificate_sources.py; src/cadrumo/application/auth/_certificate_sources_operator.py; src/cadrumo/application/auth/_operator.py; src/cadrumo/application/auth/_operator_scope.py; src/cadrumo/application/auth/_sessions.py; src/cadrumo/application/auth/tests/test_certificate_secret_backend.py; src/cadrumo/application/auth/tests/test_certificate_sources_check.py; src/cadrumo/application/auth/tests/test_operator.py; src/cadrumo/application/state_projection.py; src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`.
- [x] `W02.P07.S50` - Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py; src/cadrumo/adapters/outbound/aeat/auth/__init__.py; src/cadrumo/adapters/outbound/aeat/auth/tests`.
- [x] `W02.P07.S51` - Prove certificate secrets set, resolve, and remove only through real secure storage, force real event-commit failure after set and remove, then prove retry resumes the original operation, emits the original stable event exactly once, preserves SET versus ROTATED classification, and reports removal truthfully, and also prove no certificate keyring backend, selector, fallback, migration, probe, cleanup path, or parallel secret writer remains; `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py; src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`.
- [x] `W02.P07.S52` - Prove register, select, check, status, test, and login consume the same resolved certificate bytes; `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`.

### Phase `W02.P05` - Build resumable all-profile reset

Replace scope reset with a durable target-scoped roll-forward operation composed from canonical deletion, auth, retention, and pointer services.

- [x] `W02.P05.S54` - Add target deletion assessment and reset ownership fields to bucket-maintenance contracts; `src/cadrumo/application/bucket_maintenance/_contracts.py`.
- [x] `W02.P05.S55` - Expose target-scoped deletion assessment and verify reset operation ownership and fingerprint during deletion; `src/cadrumo/application/bucket_maintenance/_service.py`.
- [x] `W02.P05.S56` - Define the authoritative deletion-relevant bucket fingerprint for assessment and resume; `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`.
- [x] `W02.P05.S57` - Prove deletion assessment reports real retention blockers without mutating the bucket; `src/cadrumo/application/bucket_maintenance/tests/test_service_retention_floor.py`.
- [x] `W02.P05.S58` - Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence; `src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py`.
- [x] `W02.P05.S59` - Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models; `src/cadrumo/application/_config_reset_models.py`.
- [x] `W02.P05.S60` - Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal; `src/cadrumo/application/_config_reset_repository.py`.
- [x] `W02.P05.S61` - Prove reset journal atomicity, permissions, corruption refusal, exclusion, and fresh-process reload; `src/cadrumo/application/tests/test_config_reset_repository.py`.
- [x] `W02.P05.S62` - Replace scoped reset with start, status, and resume over all live, tombstoned, and dangling-pointer targets; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S63` - Acquire target locks in sorted UUID order and persist every retention decision before mutation; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S64` - Invoke target-scoped auth reset and delete canonical secure-storage certificate secrets before each target deletion without certificate keyring reconciliation or migration; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S65` - Invoke strong profile logout for the active reset target and reconcile dangling pointers through the core authority; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S66` - Persist deleting ownership before deletion and completion after each irreversible transition; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S67` - Reacquire locks and recheck fingerprints and retention during roll-forward resume without mutating on status; `src/cadrumo/application/config_reset.py`.
- [x] `W02.P05.S68` - Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults; `src/cadrumo/application/tests/test_config_reset.py`.
- [x] `W02.P05.S69` - Prove every reset phase boundary resumes honestly in a fresh child process; `src/cadrumo/application/tests/test_config_reset_recovery.py`.
- [x] `W02.P05.S70` - Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes; `src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py; src/cadrumo/adapters/persistence/storage/bucket/tests/test_lockfile.py; src/cadrumo/adapters/persistence/storage/master_key/_master_key.py; src/cadrumo/adapters/persistence/storage/master_key/_master_key_ephemeral.py; src/cadrumo/adapters/persistence/storage/master_key/_provider_session.py; src/cadrumo/application/bucket_maintenance/_service.py; src/cadrumo/application/tests/test_config_reset_concurrency.py`.

### Phase `W02.P21` - Harden passphrase and recovery custody

Expose explicit passphrase and recovery lifecycle operations while keeping mnemonic material off argv, output envelopes, and non-file custody backends.

- [x] `W02.P21.S71` - Expose distinct recovery status, create, rotate, verify, and recover application operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W02.P21.S72` - Make recovery create refuse an existing enrollment and rotate require an existing enrollment; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W02.P21.S73` - Preserve the prior recovery envelope until a candidate mnemonic has been fully verified; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W02.P21.S74` - Restrict recovery to file custody and return typed refusals for keyring and unsecured custody; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W02.P21.S75` - Preserve the established recovery fingerprint across verification and recovery operations; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`.
- [x] `W02.P21.S76` - Prove create refusal, rotate preconditions, candidate verification, and old-envelope survival with real encrypted files; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`.
- [x] `W02.P21.S77` - Prove mnemonic verification and recovery never serialize secret material; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [x] `W02.P21.S78` - Prove file-only custody and typed keyring or unsecured refusals across the custody matrix; `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`.
- [x] `W02.P21.S79` - Prove passphrase change preserves encrypted data and survives failed candidate confirmation; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`.
- [x] `W02.P21.S80` - Re-export only the explicit passphrase and recovery lifecycle operations; `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`.

## Wave `W03` - Consolidate remaining duplicated backend services

Remove evidence, export, hashing, replay, namespace, filed-capture, LLM-review, registry-projection, and duplication-runner overlap after the core profile and auth authorities are stable; the CLI Wave depends on these canonical services.

### Phase `W03.P08` - Enforce one ledger-evidence writer

Remove the generic evidence patch route and preserve invoice linking only through atomic application operations.

- [x] `W03.P08.S81` - Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer; `src/cadrumo/application/ledger/_actions_manual.py; src/cadrumo/application/ledger/__init__.py`.
- [x] `W03.P08.S82` - Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged; `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`.
- [x] `W03.P08.S83` - Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy; `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`.
- [x] `W03.P08.S224` - Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching; `src/cadrumo/application/ledger/_actions_split_merge.py; src/cadrumo/application/ledger/_llm_classification.py`.
- [x] `W03.P08.S225` - Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged; `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py; src/cadrumo/application/ledger/tests/test_llm_evidence_split.py`.

### Phase `W03.P09` - Centralize profile export

Move portable and subject-access exports onto one crash-reconcilable application service with typed purpose.

- [x] `W03.P09.S84` - Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate; `src/cadrumo/application/user_profile/_commands.py; src/cadrumo/application/user_profile/_bundle.py`.
- [x] `W03.P09.S85` - Persist non-secret profile export operation states atomically outside the target artifact; `src/cadrumo/application/user_profile/_bundle_export_operation.py`.
- [x] `W03.P09.S86` - Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery; `src/cadrumo/application/user_profile/_bundle_export.py`.
- [x] `W03.P09.S87` - Re-export the typed profile export service as the sole public export orchestration API; `src/cadrumo/application/user_profile/__init__.py`.
- [x] `W03.P09.S88` - Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [x] `W03.P09.S89` - Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events; `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.

### Phase `W03.P10` - Remove residual hashing and replay duplication

Delegate eighteen exact one-shot digests and four reducible file-hash bodies to core, add a recurrence gate, and remove the check-shaped replay backend until real replay exists.

- [x] `W03.P10.S90` - Delegate review-package recipient fingerprints to core sha256_hex; `src/cadrumo/application/modelo/_review_package_recipient_registry.py`.
- [x] `W03.P10.S91` - Prove recipient fingerprints against known vectors and encrypted registry roundtrip; `src/cadrumo/application/modelo/tests/test_review_package_recipient_registry.py`.
- [x] `W03.P10.S92` - Delegate MCP telemetry content digests to core sha256_hex; `src/cadrumo/entrypoints/mcp/_telemetry.py`.
- [x] `W03.P10.S93` - Prove telemetry UTF-8 digests against known vectors and retained-record roundtrip; `src/cadrumo/entrypoints/mcp/tests/test_telemetry_retention.py`.
- [x] `W03.P10.S226` - Delegate declaracion parser and pdfplumber one-shot PDF digests to core sha256_hex without changing byte inputs or digest representation; `src/cadrumo/adapters/inbound/declaracion/_parser.py; src/cadrumo/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`.
- [x] `W03.P10.S227` - Delegate Clave Movil, outbound LLM cache, and agent evaluation one-shot fingerprints to core sha256_hex while preserving truncation and exact encoded inputs; `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py; src/cadrumo/adapters/outbound/llm/_cache.py; src/cadrumo/agent/eval/_flywheel.py`.
- [x] `W03.P10.S228` - Delegate storage rotation, SQL engine, and calculation-sheet one-shot identifiers to core sha256_hex while preserving exact payload construction and truncation; `src/cadrumo/adapters/persistence/storage/_rotation.py; src/cadrumo/adapters/persistence/storage/sql/engine.py; src/cadrumo/application/storage/calc_sheets/_engine.py`.
- [x] `W03.P10.S229` - Delegate perception, retention, and calculation observation object-key digests to core sha256_hex while preserving the exact normalized key bytes; `src/cadrumo/application/aggregation/_percepciones_observations_repository.py; src/cadrumo/application/aggregation/_retencion_observations_repository.py; src/cadrumo/application/calculations/_observations_repository.py`.
- [x] `W03.P10.S230` - Delegate filing import, M145 communication, workflow, and submission one-shot identifiers to core sha256_hex while preserving structured inputs, truncation, and public values; `src/cadrumo/application/filing/_import.py; src/cadrumo/application/modelo/_m145_communication_records.py; src/cadrumo/application/workflow/_models.py; src/cadrumo/domain/submission/_models.py`.
- [x] `W03.P10.S231` - Delegate whole-file corpus manifest hashing to core hash_file without changing manifest semantics; `src/cadrumo/core/corpus_manifest/__init__.py`.
- [x] `W03.P10.S232` - Retain observability file-read retry semantics while delegating successful file-digest mechanics to core hash_file; `src/cadrumo/core/observability/_fingerprint.py`.
- [x] `W03.P10.S233` - Delegate local manuals file verification to core hash_file while retaining the distinct network-stream hashing path; `src/cadrumo/domain/manuals/_fetch.py`.
- [x] `W03.P10.S234` - Preserve the mirror object-key structured byte contract but delegate its one-shot digest to sha256_hex without converting it to HMAC; `src/cadrumo/adapters/outbound/storage/_mirror_manifest.py`.
- [x] `W03.P10.S235` - Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses; `src/cadrumo/core/tests/test_hashing_adoption.py`.
- [x] `W03.P10.S236` - Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities; `src/cadrumo/application/evidence/_service.py; src/cadrumo/application/evidence/__init__.py; src/cadrumo/application/evidence/tests/test_evidence.py`.

### Phase `W03.P22` - Centralize secure-object namespace authority

Make the storage namespace registry the sole declaration authority and prove every production consumer binds to it.

- [x] `W03.P22.S242` - Correct namespace registry metadata drift and make each namespace definition the sole authority for identifier, schema version, sensitivity, default object key, key grammar, owner, and custody; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py; src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`.
- [x] `W03.P22.S243` - Remove duplicate namespace, version, sensitivity, catalogue-key, and custody literals from transaction, invoice, modelo participation, and bucket persistence consumers and bind them to registry definitions; `src/cadrumo/domain/transactions/; src/cadrumo/domain/invoices/; src/cadrumo/domain/modelos/; src/cadrumo/domain/buckets/`.
- [x] `W03.P22.S244` - Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions; `src/cadrumo/application/user_profile/; src/cadrumo/application/calculations/; src/cadrumo/application/aggregation/; src/cadrumo/application/live/`.
- [x] `W03.P22.S245` - Remove duplicate namespace and custody declarations from Clave, LLM cache and usage, bundle, attachment, and secure-storage consumers without conflating certificate custody with master-key keyring custody; `src/cadrumo/adapters/outbound/aeat/auth/; src/cadrumo/adapters/outbound/llm/; src/cadrumo/application/evidence/; src/cadrumo/domain/attachments/; src/cadrumo/adapters/persistence/storage/`.
- [x] `W03.P22.S246` - Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition; `src/cadrumo/application/tests/test_namespace_registry_adoption.py`.

### Phase `W03.P23` - Centralize filed observation capture

Unify filed selection, history ordering, persistence, and route-specific failure policy without weakening strict IVA capture.

- [x] `W03.P23.S247` - Make filed observation persistence the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes and remove the duplicate selector and persistence loop from capture orchestration; `src/cadrumo/application/live/_filed_observation_persistence.py; src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `W03.P23.S248` - Introduce one typed filed-capture finalizer and failure accumulator used by single, bulk, and source capture with explicit fail-fast single and source policy and best-effort bulk policy; `src/cadrumo/application/live/_filed_data_capture.py; src/cadrumo/application/live/_filed_data.py`.
- [x] `W03.P23.S249` - Prove identical latest selection and history ordering across all capture routes, their distinct failure policies, and preservation of the separate strict IVA compensation persistence path; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py; src/cadrumo/application/live/tests/test_filed_bulk_capture.py; src/cadrumo/application/live/tests/test_iva_remote_state_acquisition.py`.

### Phase `W03.P24` - Centralize the LLM review workflow

Give one typed application workflow ownership of LLM suggestion, review, application, rejection, saturation, and split routing.

- [x] `W03.P24.S250` - Define typed LLM review requests, decisions, results, and mandatory invocation origins without an application-layer default CLI source command; `src/cadrumo/application/ledger/_llm_review_workflow.py; src/cadrumo/application/ledger/_llm_suggestions.py`.
- [x] `W03.P24.S251` - Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives; `src/cadrumo/application/ledger/_llm_review_workflow.py; src/cadrumo/application/ledger/_llm_classification.py; src/cadrumo/application/ledger/__init__.py`.
- [x] `W03.P24.S252` - Route classify --auto-split and split --llm through the typed review workflow with distinct invocation origins and remove CLI-owned review branching and application source-command defaults; `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py; src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W03.P24.S253` - Prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against real persistence and model subprocess boundaries; `src/cadrumo/application/ledger/tests/test_llm_reject.py; src/cadrumo/application/ledger/tests/test_llm_saturation.py; src/cadrumo/application/ledger/tests/test_llm_evidence_no_split.py; src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py; src/cadrumo/entrypoints/cli/tests/`.

### Phase `W03.P25` - Unify registry query resolution and projections

Share typed resolved context and projection builders while making every accepted as-of parameter effective.

- [x] `W03.P25.S254` - Introduce one typed resolved registry context shared by scoped and unscoped query methods while preserving both public resolution forms; `src/cadrumo/domain/calculations/registry/_queries.py`.
- [x] `W03.P25.S255` - Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it; `src/cadrumo/domain/calculations/registry/_queries.py; src/cadrumo/application/modelo/_registry_discovery.py`.
- [x] `W03.P25.S256` - Build describe, casilla listing, and formulas from shared typed projections while preserving separate casilla-detail and bindings reports unless code-level substitutability is proven; `src/cadrumo/domain/calculations/registry/_queries.py`.
- [x] `W03.P25.S257` - Prove scoped and unscoped parity, historical as-of boundaries, invalid-window refusal, shared projection consistency, and the intentional distinction between bindings and casilla detail; `src/cadrumo/domain/calculations/registry/tests/test_queries.py; src/cadrumo/application/modelo/tests/`.

### Phase `W03.P26` - Repair duplication audit authority

Give one platform-neutral typed runner ownership of duplication execution, parsing, and truthful availability classification.

- [x] `W03.P26.S258` - Make dev.audit.duplication the sole owner of the platform-neutral jscpd command, subprocess execution, timeout handling, output parsing, clone records, percentage, diagnostics, and typed availability result; `dev/audit/duplication.py`.
- [x] `W03.P26.S259` - Make the health report consume the typed duplication result and classify zero observed clones as green, observed clones as amber, and unavailable, failed, timed-out, non-zero, or unparseable execution as explicit amber-unavailable; `dev/audit/report.py`.
- [x] `W03.P26.S260` - Replace the shell pipeline with a direct Python duplication runner invocation so Windows and POSIX execute the same authority and retain stdout, stderr, return code, and timeout evidence; `justfile`.
- [x] `W03.P26.S261` - Prove real zero-clone, clone, unavailable executable, non-zero, timeout, stderr, and unparseable outcomes cannot become false green and that report and direct runner render the same typed result; `src/cadrumo/tests/test_dev_audit_report.py`.

## Wave `W04` - Hard-cut over the operator CLI

Replace duplicate and misleading command doors with the accepted grammar without aliases; this Wave depends on the canonical backend services from Waves W02 and W03.

### Phase `W04.P11` - Cut over profile, sandbox, and reset commands

Remove lock and sandbox-use aliases and expose the accepted logout, switch, and reset start/status/resume grammar.

- [x] `W04.P11.S96` - Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names; `src/cadrumo/entrypoints/cli/_config/_custody.py`.
- [x] `W04.P11.S97` - Remove the config profile sandbox use registration and execution path without an alias; `src/cadrumo/entrypoints/cli/_config/_sandbox.py`.
- [x] `W04.P11.S98` - Preserve config profile logout as the sole strong local-session logout command; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [x] `W04.P11.S99` - Remove config lock and its weaker session-only execution path without an alias; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [x] `W04.P11.S100` - Replace flat scoped reset registration with the config reset command group; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [x] `W04.P11.S101` - Register only reset start, status, and resume with operation, retention, reason, and confirmation options; `src/cadrumo/entrypoints/cli/_config/_reset_cli.py`.
- [x] `W04.P11.S102` - Prove exact sandbox labels work through switch while sandbox use and bare names are absent; `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`.
- [x] `W04.P11.S103` - Prove switching and strong logout through real persisted custody state; `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`.
- [x] `W04.P11.S104` - Prove reset start, status, resume, operation IDs, retention override, reasons, and confirmations across real processes; `src/cadrumo/entrypoints/cli/tests/test_config_reset_lifecycle.py`.
- [x] `W04.P11.S237` - Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI; `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py; src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py; src/cadrumo/entrypoints/cli/tests/test_profile_subject_access_request.py`.

### Phase `W04.P12` - Cut over passphrase and recovery commands

Replace rekey and overloaded recovery spellings with the accepted secure interactive and secrets-stdin lifecycle.

- [x] `W04.P12.S105` - Replace config rekey with only config passphrase change and secure input handling; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `W04.P12.S106` - Replace recovery display and rotation spellings with recovery status, create, and rotate; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `W04.P12.S107` - Register only recovery verify and flat recover with secrets-stdin and no mnemonic argv; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `W04.P12.S108` - Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit; `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`.
- [x] `W04.P12.S109` - Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths; `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`.
- [x] `W04.P12.S110` - Prove passphrase change through a real encrypted vault; `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`.
- [x] `W04.P12.S111` - Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material; `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`.
- [x] `W04.P12.S112` - Prove passphrases, mnemonics, and secret-input values are absent from help and examples; `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`.
- [x] `W04.P12.S113` - Prove secure TTY failures and strict bounded secrets-stdin JSON through localized CLI execution; `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`.
- [x] `W04.P12.S114` - Align bootstrap and repair-policy inventories with the recovery family and flat recover exception; `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`.

### Phase `W04.P13` - Cut over auth and certificate commands

Expose distinct auth logout/reset and secure-storage-only certificate secret operations without clear or backend aliases.

- [x] `W04.P13.S116` - Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.
- [x] `W04.P13.S118` - Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths; `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`.
- [x] `W04.P13.S119` - Require yes for reset start and resume while keeping status non-destructive; `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`.

### Phase `W04.P14` - Cut over ledger and audit commands

Remove ledger evidence bypass and fake replay while retaining canonical attach, invoice link, and audit check.

- [x] `W04.P14.S120` - Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [x] `W04.P14.S121` - Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check; `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`.
- [x] `W04.P14.S122` - Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar; `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`.
- [x] `W04.P14.S123` - Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events; `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.
- [x] `W04.P14.S124` - Assert the accepted root grammar exactly and reject every removed path and option; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

## Wave `W05` - Migrate contracts, locales, and documentation

Move every machine and human contract to the new grammar and regenerate owned outputs atomically after the live CLI has its final shape.

### Phase `W05.P15` - Migrate payload, token, and schema contracts

Update typed envelopes, operation mappings, write-policy tokens, and static command inventories to the hard-cutover paths.

- [x] `W05.P15.S125` - Remove schema registrations for lock, rekey, legacy recovery, and sandbox-use commands; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `W05.P15.S126` - Define secret-free schemas for passphrase change, recovery status, create, rotate, verify, and flat recover; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `W05.P15.S128` - Replace flat scoped reset with reset start, status, and resume schemas; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `W05.P15.S129` - Remove evidence-link input and evidence-update output fields from ledger link; `src/cadrumo/entrypoints/cli/_ledger_payloads.py`.
- [x] `W05.P15.S130` - Remove modelo audit replay result schema and public command key; `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`.
- [x] `W05.P15.S131` - Retire the modelo audit replayed event token after all consumers move to check results; `src/cadrumo/domain/buckets/_event.py`.
- [x] `W05.P15.S132` - Update write-policy tokens for the accepted destructive and read-only command paths; `src/cadrumo/application/storage_write_policy.py`.
- [x] `W05.P15.S133` - Update the authoritative command manifest to the accepted paths and remove legacy keys; `src/cadrumo/application/operator_surface/_manifest.py`.
- [x] `W05.P15.S134` - Update nested command-path token handling and examples for passphrase, recovery, auth, and reset groups; `src/cadrumo/entrypoints/cli/_errors.py`.
- [x] `W05.P15.S135` - Replace the rekey recovery diagnostic with config passphrase change; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W05.P15.S136` - Replace verify-recovery terminology with config recovery verify in the recovery contract; `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W05.P15.S137` - Assert exact new schema keys, removed-key absence, exclusivity, and secret-free results; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [x] `W05.P15.S138` - Update root fallback write classification without accepting removed command paths; `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`.
- [x] `W05.P15.S238` - Remove certificate backend selectors and replay-specific fields from every payload and schema projection while preserving independent master-key keyring custody contracts; `src/cadrumo/entrypoints/cli/_config_payloads.py; src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py; src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.

### Phase `W05.P16` - Migrate locales and operator metadata

Move all four locale catalogues plus help, risk, error, and MCP mirrors to the accepted grammar.

- [x] `W05.P16.S139` - Replace removed command, option, help, risk, and error nodes with accepted English grammar; `src/cadrumo/locales/en.yml`.
- [x] `W05.P16.S140` - Replace removed command, option, help, risk, and error nodes with accepted Spanish grammar; `src/cadrumo/locales/es.yml`.
- [x] `W05.P16.S141` - Replace removed command, option, help, risk, and error nodes with accepted Catalan grammar; `src/cadrumo/locales/ca.yml`.
- [x] `W05.P16.S142` - Replace removed command, option, help, risk, and error nodes with accepted Hungarian grammar; `src/cadrumo/locales/hu.yml`.
- [x] `W05.P16.S143` - Reconcile intentional identical-locale declarations after the grammar migration; `src/cadrumo/locales/_intentional_identical.json`.
- [x] `W05.P16.S144` - Require four-locale parity and reject orphaned locale nodes for removed grammar; `src/cadrumo/locales/tests/test_audit.py`.
- [x] `W05.P16.S145` - Classify passphrase, recovery, reset start and resume, portable profile export, and subject-access export under exact risk keys, with both cleartext export purposes carrying the same handoff classification; `src/cadrumo/application/operator_surface/_risk_table.py`.
- [ ] `W05.P16.S146` - Replace stale help records with accepted profile, recovery, certificate, reset, ledger, and audit descriptions; `src/cadrumo/application/operator_surface/_help.py`.
- [x] `W05.P16.S147` - Update remaining operator-surface contract notes to the accepted grammar and authority semantics; `src/cadrumo/application/operator_surface/_contract.py`.
- [x] `W05.P16.S148` - Replace flat reset and legacy custody next actions with registered accepted commands; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [x] `W05.P16.S149` - Assert operator help, risk, mutability, schema, and live-registration inventories remain exact mirrors; `src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py`.
- [x] `W05.P16.S150` - Prove suggestions resolve only to accepted registered commands; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
- [x] `W05.P16.S151` - Reject removed command strings in diagnostics, help, errors, and schema metadata; `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
- [x] `W05.P16.S152` - Replace sandbox-use identity gating with canonical config switch handling; `src/cadrumo/entrypoints/mcp/_identity_gate.py`.
- [x] `W05.P16.S153` - Derive exact nested passphrase, recovery, auth, reset, ledger, and audit inputs from accepted schemas; `src/cadrumo/entrypoints/mcp/_input_schema.py`.
- [x] `W05.P16.S154` - Remove legacy MCP tool keys and dispatch only accepted CLI mirrors; `src/cadrumo/entrypoints/mcp/_tools.py`.
- [x] `W05.P16.S155` - Assert MCP descriptors and dispatch mirror accepted keys and reject removed keys; `src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`.
- [x] `W05.P16.S156` - Assert MCP risk annotations match the operator risk table; `src/cadrumo/entrypoints/mcp/tests/test_risk_table_parity.py`.
- [x] `W05.P16.S157` - Assert MCP mutability distinguishes read-only status from destructive operations; `src/cadrumo/entrypoints/mcp/tests/test_write_policy_mutability_parity.py`.
- [x] `W05.P16.S158` - Prove canonical switch identity gating and removed sandbox-use unavailability; `src/cadrumo/entrypoints/mcp/tests/test_identity_gate.py`.
- [x] `W05.P16.S159` - Prove generated MCP input schemas for every accepted changed command; `src/cadrumo/entrypoints/mcp/tests/test_input_schema.py`.
- [x] `W05.P16.S160` - Refresh command-search expectations only for accepted keys and reject removed tokens; `src/cadrumo/application/command_search/tests/test_command_ranking_golden.py`.
- [x] `W05.P16.S223` - Re-arm MCP identity confirmation when canonical profile logout clears the active taxpayer; `src/cadrumo/entrypoints/mcp/_identity_gate.py; src/cadrumo/entrypoints/mcp/tests/test_identity_gate.py`.

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
- [ ] `W05.P17.S239` - Rewrite profile export and subject-access documentation around the shared durable service, schema-derived categories, equivalent cleartext handoff risk, and separate sealed recovery archive; `docs/how-to/profile-setup.md; docs/reference/import-export-and-evidence.md; docs/reference/commands-and-configuration.md`.
- [ ] `W05.P17.S240` - Remove evidence audit replay from all user documentation, generated reference expectations, examples, and terminology projections while retaining audit check; `docs/; dev/docs/; src/cadrumo/_data/terminology/`.

## Wave `W06` - Prove conformance and close the campaign

Run focused real-behavior evidence, whole-surface conformance, duplication re-audit, formal review, and requirement-by-requirement closure after all prior Waves land.

### Phase `W06.P18` - Run focused real-behavior verification

Exercise every canonical authority with real encrypted storage, processes, locks, certificate services, and CLI invocation.

- [ ] `W06.P18.S177` - Run focused pointer, switch, logout, reset, and bootstrap-policy suites against real persisted state; `src/cadrumo/entrypoints/cli/tests/`.
- [x] `W06.P18.S178` - Run passphrase and recovery lifecycle suites against real encrypted vaults and secure input channels; `src/cadrumo/entrypoints/cli/_config/tests/`.
- [x] `W06.P18.S179` - Run auth and certificate suites against real storage and provider boundaries; `src/cadrumo/application/auth/tests/`.
- [x] `W06.P18.S180` - Run ledger attach, atomic invoice-link, LLM split inheritance, and failure-rollback suites and prove no generic evidence bypass or partial child commit can execute; `src/cadrumo/application/ledger/tests/`.
- [x] `W06.P18.S181` - Run application and live CLI profile-export suites across real fresh processes, target contention, schema-derived SAR categories, and every crash window; `src/cadrumo/application/user_profile/tests/; src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py; src/cadrumo/entrypoints/cli/tests/test_profile_subject_access_request.py`.
- [x] `W06.P18.S182` - Run evidence service and modelo audit suites and prove the replay method, command, schema, event, tests, and documentation cannot execute or be discovered; `src/cadrumo/application/evidence/tests/test_evidence.py; src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.
- [x] `W06.P18.S183` - Run MCP dispatch, identity, input-schema, risk, mutability, and telemetry parity suites; `src/cadrumo/entrypoints/mcp/tests/`.
- [x] `W06.P18.S241` - Run hashing vector, truncation, file-retry, network-stream, mirror-key, and AST recurrence suites for all 18 one-shot and four reducible call sites; `src/cadrumo/core/tests/; src/cadrumo/adapters/; src/cadrumo/application/; src/cadrumo/domain/; src/cadrumo/entrypoints/mcp/tests/`.
- [x] `W06.P18.S262` - Run namespace registry and non-vacuous production adoption suites and reject duplicate declarations across every production root; `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py; src/cadrumo/application/tests/test_namespace_registry_adoption.py`.
- [x] `W06.P18.S263` - Run filed single, bulk, source, history-ordering, and strict IVA suites against real persisted observations and artefacts; `src/cadrumo/application/live/tests/`.
- [x] `W06.P18.S264` - Run the typed LLM review workflow and both CLI routing modes against real persistence and subprocess model boundaries; `src/cadrumo/application/ledger/tests/; src/cadrumo/entrypoints/cli/tests/`.
- [x] `W06.P18.S265` - Run scoped and unscoped registry query suites across historical as-of boundaries and projection parity; `src/cadrumo/domain/calculations/registry/tests/; src/cadrumo/application/modelo/tests/`.
- [x] `W06.P18.S266` - Run the direct duplication runner and health-report suites and prove every unavailable or malformed execution is visibly amber rather than green; `src/cadrumo/tests/test_dev_audit_report.py`.

### Phase `W06.P19` - Run whole-surface conformance and duplication audits

Materialize the CLI, prove schema, locale, docs, and MCP agreement, rerun clone and semantic duplication checks, and execute attributable quality gates.

- [ ] `W06.P19.S185` - Materialize the complete lazy CLI tree in a fresh process and assert every leaf path is unique; `src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`.
- [ ] `W06.P19.S186` - Compare the materialized tree with the accepted additions and removals and fail on unplanned leaf loss; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.
- [ ] `W06.P19.S187` - Run documented-command path and argument conformance against the live tree; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `W06.P19.S188` - Run JSON schema registration and output conformance for every live leaf; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [ ] `W06.P19.S189` - Run self-referential CLI string conformance and reject every removed spelling; `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
- [x] `W06.P19.S190` - Run suggestion and next-action conformance against the live tree; `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
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
- [ ] `W06.P19.S203` - Run the authoritative typed duplication runner and require zero clones for green, clone findings for amber, and unavailable, failed, timed-out, non-zero, or unparseable execution for explicit amber-unavailable without false green; `dev/audit/duplication.py; dev/audit/report.py; justfile`.
- [ ] `W06.P19.S204` - Dispatch a fresh Luna xhigh agent swarm over every audited functionality cluster; `src/cadrumo/`.
- [ ] `W06.P19.S205` - Rerun Vaultspec-RAG semantic searches across certificate custody, ledger evidence, export, hashing, replay, namespaces, filed capture, LLM review, registry queries, and duplication infrastructure; `src/cadrumo/; dev/audit/`.
- [ ] `W06.P19.S206` - Confirm every semantic candidate with exact declaration, import, export, caller, writer, persistence, CLI, schema, locale, test, documentation, and generated-artifact searches before classification; `src/cadrumo/; dev/; docs/; .github/; justfile`.
- [ ] `W06.P19.S207` - Record canonical owner, surviving consumers, removed declarations, bypass disposition, and non-vacuous adoption evidence for every amended functionality cluster; `.vault/audit/`.
- [ ] `W06.P19.S208` - Record unrelated concurrent failures separately without claiming global green; `.vault/exec/`.

### Phase `W06.P20` - Perform formal review and completion audit

Run the formal code-review skill, reconcile findings, and prove every accepted ADR requirement before declaring completion.

- [ ] `W06.P20.S209` - Invoke vaultspec-code-review over the complete feature diff for safety, intent, boundary direction, and test quality; `.`.
- [ ] `W06.P20.S210` - Resolve every in-scope blocker or major finding through its owning implementation Step; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S211` - Rerun every focused or full gate invalidated by a corrective edit; `.vault/exec/`.
- [ ] `W06.P20.S212` - Record a zero-blocker and zero-major formal review verdict; `.vault/audit/`.
- [x] `W06.P20.S213` - Confirm every closed implementation Step has an attributable execution record; `.vault/exec/`.
- [ ] `W06.P20.S214` - Confirm no removed CLI spelling survives in source, locales, tests, docs, schemas, MCP, or suggestions; `.`.
- [ ] `W06.P20.S215` - Confirm certificate custody, ledger evidence, portable export, hashing, namespaces, filed capture, LLM review, registry projection, and duplication execution each have one canonical owner and no parallel writer, resolver, parser, or command path; `src/cadrumo/; dev/audit/`.
- [ ] `W06.P20.S216` - Audit every amended ADR decision, including delete-only certificate cutover, atomic ledger evidence, live export routing, 18 plus 4 hashing consolidation, backend replay removal, namespace adoption, filed capture, LLM review, registry as-of behavior, and truthful duplication infrastructure, against code and objective evidence; `.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md`.
- [ ] `W06.P20.S217` - Rebuild the feature index after all plan, execution, audit, ADR, research, and reference artifacts are final; `.vault/`.
- [ ] `W06.P20.S218` - Run the plan structural check and refuse closure while any Step remains open or malformed; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [x] `W06.P20.S219` - Run feature-scoped Vaultspec checks and resolve every attributable finding; `.vault/`.
- [x] `W06.P20.S220` - Run repository-wide Vaultspec checks and triage unrelated residuals honestly; `.vault/`.
- [x] `W06.P20.S221` - Run the required fresh-context campaign-close honesty review with explicit audits for duplicated authority, vacuous adoption tests, ignored accepted parameters, partial transaction commits, and false-green quality infrastructure; `.vault/audit/`.
- [ ] `W06.P20.S222` - Mark the plan complete only after every Step, record, gate, blocker, and major finding is closed; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S267` - Verify each open W05 Step against its named surface before checking it, never inferring satisfaction from the live command tree alone; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S268` - Complete the W06.P18 and W06.P19 evidence, refusing to close any Step whose execution record lacks a command, a non-zero collected count, an exit line, and a HEAD reference; `.vault/exec/`.
- [ ] `W06.P20.S269` - Decide in a follow-on ADR the criterion by which a command path is profile-bound, then reconcile the 48 unguarded mutation-shaped leaves against it per verb; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `W06.P20.S270` - Remove the permissive not-read-only default for unknown command keys, or prove every gate resting on it still discriminates an absent key from a live write verb; `src/cadrumo/application/operator_surface/_classification.py`.
- [x] `W06.P20.S271` - Assert structurally that an execution record carries a populated Outcome before its Step may be checked, since the vault check passes empty scaffolds; `.vault/exec/`.
- [x] `W06.P20.S272` - Commit the plan file alongside execution records in every closure commit, and land the 31 closures currently held only in the working tree; `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`.
- [ ] `W06.P20.S273` - Make a stale import-linter ignore fail loudly and distinctly from a contract breach, so an aborted run cannot read as a quiet one; `.importlinter`.
- [ ] `W06.P20.S274` - Resolve the two broken layered contracts with their owning campaigns, without widening the ignore list; `.importlinter`.
- [x] `W06.P20.S275` - Teach the documented-command conformance parser to recognise a blocked-row marker rather than reading its prose as a command path; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `W06.P20.S276` - Attribute the two P18 failures before any closure, 8 in the passphrase and recovery lifecycle suite and 22 in the MCP parity suite, separating the expected keychain remainder from real defects; `src/cadrumo/entrypoints/cli/_config/tests/; src/cadrumo/entrypoints/mcp/tests/`.
- [x] `W06.P20.S277` - Seed the profile-key registry on the MCP path itself rather than relying on a wizard import side effect, and prove whoami through a real stdio subprocess client; `src/cadrumo/entrypoints/mcp/`.
- [ ] `W06.P20.S278` - Give the namespace-registry adoption gate an anti-vacuity floor and every production root, since it currently finds zero subjects and asserts an empty list; `src/cadrumo/application/tests/test_namespace_registry_adoption.py`.
- [x] `W06.P20.S279` - Refer the config CLI module size breach to the peer TUI campaign that caused it, since the module stood at 1254 lines inside budget before the manager-from-create commit added 134; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [x] `W06.P20.S280` - Remove the retired evidence-bundle replay from the modelo-390 records-audit sequence prose, which contradicts its own blocked annotation; `docs/_sequences/contracts/how-to/modelo-390/`.
- [x] `W06.P20.S281` - Resolve the seven unallowlisted tokens reddening the period combined-string gate at HEAD; `src/cadrumo/tests/`.
- [x] `W06.P20.S282` - Remove the two Code-Stands-Alone violations, a feature tag in a hashing test docstring and vault stems in the duplication disposition fields; `src/cadrumo/core/tests/test_hashing_adoption.py; dev/audit/duplication_dispositions.toml`.
- [ ] `W06.P20.S283` - Give every set-asserting gate an anti-vacuity floor, asserting the subject count is non-zero before asserting the property, across the write-guard parity, namespace-adoption and tree-walk gates; `src/cadrumo/`.
- [ ] `W06.P20.S284` - Assert the accepted period tokens on the error envelope structured context rather than on rendered prose, so a wording pass cannot red the grammar cases; `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py`.
- [ ] `W06.P20.S285` - Ground the HITL confirmation key against the live descriptor set at the gate itself, so the permissive default cannot auto-approve an unclassified mutation if a future caller passes an unvalidated key; `src/cadrumo/entrypoints/mcp/_hitl.py`.
- [ ] `W06.P20.S286` - Return the operator-output test probe and the wizard results schemas to their owning campaigns, since a test module registering a production schema key breaks 128 assertions and 19 setup errors while untracked; `src/cadrumo/application/operator_output/; src/cadrumo/application/wizard/`.
- [ ] `W06.P20.S287` - Identify the docs-lane workers reporting node-down abnormal termination, four at 24 workers and two at 4, letting a parallel run complete rather than killing it and capturing verbosely so each worker's lines are attributable; `dev/docs/tests/test_docs_build.py`.
- [x] `W06.P20.S288` - Retire the M100 casilla-accessor hand-copy onto the public numeric_casilla_value it duplicates, in a module already importing both that ops module and the error class the copy raises; `src/cadrumo/domain/calculations/registry/_formula_runtime.py`.
- [x] `W06.P20.S289` - Route the modelo evidence-covers-snapshot copy onto the public assert_evidence_covers_snapshot, and retire the cross-package private import the aggregation test uses to reach it; `src/cadrumo/application/modelo/_verification_actions.py; src/cadrumo/application/aggregation/tests/test_ledger_filing_evidence.py`.
- [ ] `W06.P20.S290` - Give the byte-identical FTS or-group builder one shared leaf home, since both copies sit in application packages that may not reach into each other; `src/cadrumo/application/command_search/_index.py; src/cadrumo/application/corpus_search/_lexical_index.py`.
- [ ] `W06.P20.S291` - Route the filing export-field overlap predicate onto the registry copy, the only admissible canonical home across that layer boundary; `src/cadrumo/application/filing/_export.py`.
- [ ] `W06.P20.S292` - Extract the shared journal-repository file substrate, noting the two classes are constraint-shape divergent so this is extraction rather than replacement; `src/cadrumo/application/config_reset.py; src/cadrumo/application/user_profile/_bundle_export_operation.py`.
- [x] `W06.P20.S293` - Escalate to the owning TUI campaign that the committed wizard package initialiser imports an untracked results module, so a clean checkout of HEAD cannot import the wizard or run the shipped CLI; `src/cadrumo/application/wizard/__init__.py`.
- [x] `W06.P20.S294` - Land the proven MCP identity seeding fix once the wizard results module is committed, so both transports report the same schema count and the parity assertion is no longer comparing two equally blind sets; `src/cadrumo/entrypoints/mcp/_server.py; src/cadrumo/entrypoints/mcp/_harness_tools.py; src/cadrumo/application/wizard/_compiler.py`.
- [x] `W06.P20.S295` - Closed as unnecessary, a peer fix bridged the payload-name filter by importing the wizard result classes into a walked module, so enrolment is filename-filtered still and the divergence ended when that bridge landed; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [ ] `W06.P20.S296` - Guard the load-bearing wizard schema re-exports against a tidy-up deletion, since the re-export idiom looks redundant and removing it silently drops both profile verbs from the MCP surface; `src/cadrumo/entrypoints/cli/_config_payloads.py`.

## Description

Execute the accepted decisions in `2026-07-15-cli-authority-verb-conformance-adr.md`, grounded by `2026-07-15-cli-authority-verb-conformance-research.md` and `2026-07-15-cli-authority-verb-conformance-reference.md`. The campaign first preserves the repaired import-linter graph and repairs the false-green duplication runner, then removes duplicated backend authorities, and only then hard-cuts the small approved set of misleading or duplicate CLI doors. Backend consolidation covers profile and auth state, certificate custody, evidence, portable export, hashing, replay, namespace metadata, filed capture, LLM review, and registry report projection. The cutover includes every machine and human contract and introduces no aliases, hidden registrations, compatibility parsers, fake replay behavior, or parallel write paths.

The work deliberately does not rename the broader 282-leaf CLI for style alone. Each accepted rename closes a duplicate or materially misleading authority: lock becomes strong profile logout, sandbox use collapses into switch, ambiguous reset becomes a resumable all-profile reset lifecycle, rekey and recovery commands become explicit custody operations, auth clear splits into logout and reset, ledger link becomes invoice-only, and audit replay is removed until genuine replay exists.

## Steps

## Parallelization

- Waves execute in order. Wave W01 is a hard prerequisite: no backend or CLI work begins until the focused tests and the fresh uncached five-contract import graph are green.
- Within Wave W01, the IRNR and invoice boundary repairs may proceed in parallel with the ratchet test repair, but `.importlinter` has one owner and the final `199/78/2` proof runs only after every boundary change lands.
- Within Wave W02, pointer and logout work lands before auth and reset composition. Auth and certificate Phases may proceed in parallel on disjoint files. Reset repository and maintenance contracts may be prepared in parallel, but reset orchestration waits for pointer, logout, auth, and certificate authorities.
- Within Wave W03, ledger evidence, profile export, hashing/replay, namespace authority, filed capture, LLM review, registry projection, and duplication infrastructure may run in parallel only where their exact file ownership is disjoint. The ledger evidence Phase precedes the LLM review Phase where both touch split persistence. The duplication recipe Step waits for ownership of the peer-modified `justfile`. Each Phase lands with its real-behavior tests.
- Waves W04 and W05 form one indivisible hard-cutover batch. There is no merge, release, or compatibility checkpoint between command removal and schema, locale, MCP, test, and documentation migration.
- Checked W04/W05 logout rows and their working-tree records predate this amended sequencing contract. They are carried as provisional historical evidence only: they do not authorize later-wave execution, do not satisfy the final cutover checkpoint, and must be reconciled, committed, and rerun after their W02/W03 backend prerequisites land.
- Locale files have distinct owners and may be updated in parallel. Generated documentation is regenerated only after the live command tree, schemas, locales, and MCP surface are final.
- No two agents edit the same source, test, locale, generated output, documentation file, or Vault artifact concurrently. Existing peer changes, including changes in `_calculation_actions.py`, are preserved; no stash, reset, checkout, or unrelated cleanup is permitted.
- Wave W06 begins after code and documentation freeze. Read-only conformance, duplication, and static checks may run in parallel, while unit and integration lanes retain their prescribed isolation. Any corrective edit reopens its owning Step and invalidates dependent evidence.

## Verification

- A fresh `lint-imports --no-cache` process keeps all five contracts, reports no unmatched ignore, and the non-vacuous ledger ratchet freezes `199` application edges, `78` application-source wildcards, and `2` test-only domain edges.
- Targeted real-behavior suites prove one atomic pointer writer, strong logout, target-scoped auth logout/reset, delete-only certificate custody, durable all-profile reset, one ledger-evidence writer, crash-reconcilable export, canonical hashing, one namespace authority, one filed-capture finalizer, typed LLM review routing, shared registry projections, and truthful duplication execution.
- Exact searches and real secure-storage tests prove the certificate keyring backend, selector, migration, reconciliation, fallback, certificate-specific native jobs, tests, locales, schemas, and documentation are absent while independent master-key OS-keyring custody remains supported.
- The materialized CLI tree equals the accepted grammar exactly and contains no duplicate path, old alias, hidden registration, compatibility parser, removed option, or unplanned leaf loss.
- Payload schemas, write policy, risk/help metadata, error suggestions, all four locales, MCP mirrors, authored documentation, generated references, static CLI tree, and sequence artifacts agree with the live command tree.
- Passphrases, recovery mnemonics, and secret-input values never appear in argv, result envelopes, logs, help, examples, or generated documentation.
- Focused Ruff, pytest, documentation, feature-surface, Vaultspec, uncached import-linter, full collection, unit, integration, and duplication gates have attributable recorded outcomes. Duplication is GREEN only after the intended production tree was observed with a valid zero result; failed or unparseable execution is explicit AMBER-unavailable.
- A fresh Luna xhigh swarm and Vaultspec-RAG semantic audit find no second declaration, dormant compatibility route, or parallel writer in any audited functionality cluster; every candidate has a recorded canonical owner and disposition.
- Formal `vaultspec-code-review` reports zero blocker and zero major findings, the fresh-context honesty review passes, every accepted ADR requirement has objective evidence, and every Step has an execution record before the plan is marked complete.
