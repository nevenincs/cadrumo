---
tags:
  - '#plan'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
tier: L3
related:
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
  - '[[2026-05-22-secure-storage-api-review-audit]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-22-secure-object-backlog-drain-r3-plan]]'
  - '[[2026-05-28-centralized-output-redaction-plan]]'
  - '[[2026-06-02-centralized-output-redaction-audit]]'
  - '[[2026-05-21-fresh-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
  - '[[2026-05-21-fresh-cli-persona-capability-gap-design-research]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-secure-storage-settings-env-audit]]'
  - '[[2026-05-26-secure-storage-migration-review-audit]]'
  - '[[2026-05-26-secure-storage-convention-regrounding-audit]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-coverage-audit]]'
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

Retired steps: `S422`, `S423`.

# `secure-storage-production-hardening` `refactor` plan

## Wave `W01` - custody and route fail-closed foundation

This Wave makes unsafe storage states fail closed before higher-level API work begins. It closes silent enrollment, missing custody verbs, session freshness gaps, unsecured backend activation, and production database-route bypasses.

### Phase `W01.P01` - explicit custody command surface

Expose and enforce the accepted profile lifecycle custody path so encrypted state can be created through profile creation and used only after profile switch opens a valid session.

- [x] `W01.P01.S01` - remove lazy master-key minting outside explicit enrollment; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W01.P01.S02` - wire custody lifecycle through profile create, profile switch, and profile logout flows; `src/aeat/application/wizard/_commands.py`.
- [x] `W01.P01.S03` - replace dead security-command and deprecated init guidance with profile lifecycle guidance; `src/aeat/adapters/persistence/storage`.
- [x] `W01.P01.S04` - add real-behavior custody CLI tests for profile create enrollment, profile switch unlock, profile logout, and retired init refusal; `src/aeat/entrypoints/cli`.

### Phase `W01.P02` - bucket key schedule and route guards

Make key material and repository routing bucket-scoped, fresh, and production-safe at the persistence boundary.

- [x] `W01.P02.S05` - introduce distinct per-bucket DEK unwrap into BucketSession activation; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W01.P02.S06` - centralize idle-lock freshness checks at active key resolution; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W01.P02.S07` - source idle-lock duration from settings or bucket manifest instead of hard-coded defaults; `src/aeat/adapters/persistence/storage/bucket`.
- [x] `W01.P02.S08` - enforce unsecured-backend refusal at activation and secure-object read-write boundaries; `src/aeat/adapters/persistence/storage`.
- [x] `W01.P02.S09` - reject explicit database URL writes from normal operator command paths; `src/aeat/core/config.py`.
- [x] `W01.P02.S10` - add route-guard regression tests for root fallback and explicit database URLs; `src/aeat/entrypoints/cli`.

## Wave `W02` - runtime API and repository enrollment

This Wave creates the production storage API boundary and migrates application code away from direct physical-store construction. Later namespace and revision work depends on this runtime boundary.

### Phase `W02.P03` - storage runtime contract

Define the runtime object that owns bucket session readiness, route attachment, repository factories, namespace policy, and storage diagnostics.

- [x] `W02.P03.S11` - add StorageRuntime models and readiness result types; `src/aeat/adapters/persistence/storage`.
- [x] `W02.P03.S12` - add bucket-attached repository factory methods to the storage runtime; `src/aeat/adapters/persistence/storage`.
- [x] `W02.P03.S13` - route profile aggregate repositories through the storage runtime; `src/aeat/application/user_profile`.
- [x] `W02.P03.S14` - route profile state projection reads through runtime readiness; `src/aeat/application/user_profile`.

### Phase `W02.P04` - consumer repository enrollment

Move profile-bound domain repositories behind runtime construction so application code no longer owns physical secure-object routing.

- [x] `W02.P04.S15` - enroll ledger and invoice repositories in runtime-created secure storage; `src/aeat/application/ledger`.
- [x] `W02.P04.S16` - enroll filing and modelo work-unit repositories in runtime-created secure storage; `src/aeat/application/modelo`.
- [x] `W02.P04.S17` - enroll AEAT pull, wallet, and live snapshot repositories in runtime-created secure storage; `src/aeat/application/live`.
- [x] `W02.P04.S18` - enroll auth session and remote provider repositories in runtime-created secure storage; `src/aeat/adapters`.
- [x] `W02.P04.S19` - add a policy guard against direct production SecureObjectRepository construction; `src/aeat/adapters/persistence/storage`.

## Wave `W03` - namespace registry and schema policy

This Wave makes namespace constants auditable architecture values. It defines ownership, sensitivity, schema, retention, key grammar, partial-read policy, and migration policy for every secure-object namespace.

### Phase `W03.P05` - central namespace registry

Create the typed registry and migrate constants to it without changing encrypted payload semantics.

- [x] `W03.P05.S20` - define secure-object namespace registry models; `src/aeat/adapters/persistence/storage`.
- [x] `W03.P05.S21` - register profile, ledger, invoice, filing, wallet, and calculation namespaces; `src/aeat/adapters/persistence/storage`.
- [x] `W03.P05.S22` - register auth, session, cache, evidence, inventory, and remote-sync namespaces; `src/aeat/adapters/persistence/storage`.
- [x] `W03.P05.S23` - replace local namespace string constants in application repositories with registry entries; `src/aeat/application`.

### Phase `W03.P06` - namespace policy enforcement

Apply registered namespace policy to repository creation, reads, writes, repair diagnostics, and source resolver degradation.

- [x] `W03.P06.S24` - require namespace registry entries when constructing runtime repositories; `src/aeat/adapters/persistence/storage`.
- [x] `W03.P06.S25` - enforce registered sensitivity and schema policy on secure-object reads and writes; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W03.P06.S26` - replace repair namespace marker heuristics with registry ownership metadata; `src/aeat/application/repair_integrity.py`.
- [x] `W03.P06.S27` - add registry completeness tests for every discovered secure-object namespace; `src/aeat/adapters/persistence/storage`.

## Wave `W04` - revision lineage and fail-closed integrity

This Wave adds storage-level mutation history and makes incomplete sensitive reads explicit. It depends on the runtime and namespace registry because lineage and read policy are namespace-scoped contracts.

### Phase `W04.P07` - secure-object revision metadata

Add lineage fields and write contracts so overwrites become traceable revisions or explicit conflicts.

- [x] `W04.P07.S28` - extend the secure-object ORM with revision and integrity metadata fields; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W04.P07.S29` - write revision ids, previous revision references, hashes, timestamps, and provenance on secure-object saves; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W04.P07.S30` - add compare-and-swap conflict handling for revision-aware writes; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W04.P07.S31` - add migration or bootstrap handling for existing rows without revision metadata; `src/aeat/adapters/persistence/storage/sql`.

### Phase `W04.P08` - fail-closed listing and source degradation

Make partial reads opt-in and propagate unreadable-row diagnostics into calculation readiness.

- [x] `W04.P08.S32` - make default sensitive namespace listing fail closed on unreadable rows; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W04.P08.S33` - stream iter_records_with_failures in bounded batches; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W04.P08.S34` - propagate storage degradation diagnostics from source resolvers to the calculation mesh; `src/aeat/application`.
- [x] `W04.P08.S35` - add real-behavior tests for unreadable-row fail-closed and explicit partial reads; `src/aeat/adapters/persistence/storage`.

## Wave `W05` - side-store and remote mirror hardening

This Wave removes or records remaining alternate persistence classes after the core runtime, namespace, and revision contracts exist. It also constrains remote storage to encrypted mirror semantics.

### Phase `W05.P09` - bucket-local side-store resolution

Migrate sensitive JSON and JSONL stores to secure objects or persist accepted exception ADRs before further expansion.

- [x] `W05.P09.S36` - inventory evidence, ledger, inventory, live, and snapshot bucket-local JSON stores; `src/aeat/application`.
- [x] `W05.P09.S37` - migrate evidence bundle persistence behind runtime-created secure-object repositories; `src/aeat/application/evidence`.
- [x] `W05.P09.S38` - migrate inventory persistence behind runtime-created secure-object repositories; `src/aeat/application/inventory`.
- [x] `W05.P09.S39` - migrate live snapshot persistence behind runtime-created secure-object repositories; `src/aeat/application/live`.
- [x] `W05.P09.S40` - persist exception ADRs for any retained explicit export or operational side store; `.vault/adr`.

### Phase `W05.P10` - remote ciphertext mirror contract

Constrain remote providers to encrypted object mirroring with revision and integrity metadata, never plaintext application state.

- [x] `W05.P10.S41` - add remote mirror policy fields to namespace registry entries; `src/aeat/adapters/persistence/storage`.
- [x] `W05.P10.S42` - store remote mirror manifests with ciphertext hashes and revision watermarks; `src/aeat/adapters`.
- [x] `W05.P10.S43` - detect partial upload, partial download, stale mirror, and revision conflicts; `src/aeat/adapters`.
- [x] `W05.P10.S44` - add real-behavior remote mirror tests using opaque encrypted payloads; `src/aeat/adapters`.
- [x] `W05.P10.S426` - wire remote mirror inspection into the operator sync path and fail or degrade on partial upload, partial download, stale mirror, and revision conflicts; `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py src/aeat/adapters/outbound/storage`.
- [x] `W05.P10.S427` - extend remote mirror manifest lineage or apply a conservative conflict rule so stale mirrors cannot be confused with divergent older root revisions; `src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py`.

## Wave `W06` - adverse-condition gates and closeout

This final Wave proves the refactor works under adverse production conditions and persists the review trail before the SecureStorage API is treated as hardened.

### Phase `W06.P11` - production adverse-condition verification

Exercise the final storage architecture with real code paths, real encrypted stores, and explicit failure assertions.

- [x] `W06.P11.S45` - add adverse-condition tests for locked, expired, wrong-passphrase, and torn-manifest sessions; `src/aeat/adapters/persistence/storage`.
- [x] `W06.P11.S46` - add adverse-condition tests for route mismatch, unregistered namespace, and unsecured backend refusal; `src/aeat/adapters/persistence/storage`.
- [x] `W06.P11.S47` - add adverse-condition tests for revision conflicts and partial remote mirrors; `src/aeat/adapters`.
- [x] `W06.P11.S48` - run focused storage, config, profile, live, ledger, modelo, and remote provider test gates; `src/aeat`.
- [x] `W06.P11.S49` - run final SecureStorage code review and persist audit closeout; `.vault/audit`.
- [x] `W06.P11.S428` - run repo-native live Google Drive mirror verification against the configured app-owned Drive contents after OAuth session readiness, and preserve connector evidence for Drive hierarchy plus calc-sheets formula/value reads; `src/aeat/adapters/outbound/storage/test_google_drive_live.py src/aeat/adapters/outbound/google src/aeat/entrypoints/cli/_config/_google.py .vault/audit`.
- [x] `W06.P11.S429` - fix calc-sheets strict PullResult metadata handling and rerun registry-backed export/pull validation; `src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google src/aeat/application/storage/calc_sheets`.
- [x] `W06.P11.S430` - blocked-on-interactive OAuth consent: complete active-profile Google OAuth login/session persistence after desktop client registration, then rerun the repo-native read-only probe and live Drive provider tests; `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py src/aeat/adapters/outbound/google src/aeat/adapters/outbound/storage/test_google_drive_live.py`.
- [x] `W06.P11.S431` - complete full workbook export proof and quota-aware handling after the observed Google Sheets 429, preserving bounded formula/value evidence for the configured app-owned calc-sheets workbook; `src/aeat/adapters/outbound/google src/aeat/application/storage/calc_sheets .vault/audit`.
- [x] `W06.P11.S432` - fix secure-object deterministic lookup regression so natural-key save/load, upsert convergence, profile records, Google folder config, and mirror archive raw keys use HashedLookup with legacy key migration; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/sql/_orm.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py`.
- [x] `W06.P11.S433` - fix access-gate authorization directory-mode export drift so the AEAT CLI imports before Google folder and live validation commands run; `src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_authorization.py src/aeat/tests/test_modelo_authorization_gate.py src/aeat/entrypoints/cli/test_root_help_shape.py`.
- [x] `W06.P11.S434` - make live Google Drive tests open a real active-profile storage session and fail enabled provider-build failures instead of skipping storage readiness; `src/aeat/adapters/outbound/storage/test_google_drive_live.py src/aeat/adapters/outbound/google/test_oauth_live.py .vault/audit`.
- [x] `W06.P11.S435` - fix Modelo 202 quota-base dependency wiring so registry-backed calc-sheets validation loads the committed registry without stale 1P source coverage defects; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes src/aeat/domain/calculations/registry/test_modelo_202_registry.py`.
- [x] `W06.P11.S436` - fix relation prefill so a missing prior filing leaves only that relation operator-manual instead of suppressing independently resolvable relation values; `src/aeat/application/calculations/_relation_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W06.P11.S437` - wrap legacy EncryptedString lookup-migration UTF-8 decode failures in AEAT DecryptionError and cover the corrupted-plaintext path with real crypto; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`.
- [x] `W06.P11.S438` - model the Modelo 202 1P quota-base previous-year source coverage or add an explicit registry gate so the legal hook is not left as comment-only operator-manual behavior; `src/aeat/_data/registry/aeat/modelos/200 src/aeat/_data/registry/aeat/modelos/202 src/aeat/domain/calculations/registry/test_modelo_202_registry.py .vault/audit`.
- [x] `W06.P11.S439` - tighten remote mirror provider metadata comparison so upload and download inspection detect namespace, object-key, byte-length, and content-hash drift against manifest entries; `src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py .vault/audit`.
- [x] `W06.P11.S440` - resolve S43-005 by preserving secure-object revision ancestry in raw mirror manifests so stale mirrors more than one revision behind are classified without timestamp-only ambiguity; `src/aeat/adapters/persistence/storage/sql src/aeat/adapters/outbound/storage .vault/audit`.
- [x] `W06.P11.S441` - record 2026-06-03 continuation proof for live Drive hierarchy, Sheets export/value reads, quota behavior, and focused validation after S428-S431/S440 remediation; `src/aeat/adapters/outbound/storage src/aeat/adapters/outbound/google src/aeat/application/calculations .vault/exec .vault/audit`.

## Wave `W07` - classified secure-SQL hygiene backlog adoption

This Wave adopts the remaining classified secure-SQL hygiene backlog into the production hardening plan. It requires inventory and research-backed slice selection before any repair rows are executed, preserving settings-backed isolation and real-behavior test discipline.

### Phase `W07.P12` - classified backlog inventory

Reconcile the remaining classified files with the accepted R1 through R3 repair pattern, identify the next bounded repair slice, and require research or execution notes where repository boundaries are unclear.

- [x] `W07.P12.S50` - Inventory remaining classified secure-SQL hygiene files and write a research-backed slice map; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [x] `W07.P12.S51` - Select the next application or CLI hygiene slice after runtime-readiness implications are researched; `src/aeat/application`.
- [x] `W07.P12.S52` - Validate candidate isolation patterns against settings-backed repository injection before repair; `src/aeat/tests`.
- [x] `W07.P12.S53` - Select the next domain repository hygiene slice after inventory confirms ownership; `src/aeat/domain`.

### Phase `W07.P13` - classified backlog gates

Close each adopted hygiene slice only after focused tests, the secure-SQL guard, and a review audit prove the slice used real code paths without monkeypatch, fake, stub, or naked environment shortcuts.

- [x] `W07.P13.S54` - Run the secure-SQL guard and focused repaired-slice tests for the first adopted slice; `commit `177f0669a` passed the secure-SQL helper tests, the ephemeral-key hygiene guard, and the focused repaired-slice suite; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/test_secure_sql.py`.
- [x] `W07.P13.S55` - Persist hygiene review and remaining-backlog closeout after each adopted slice; `.vault/audit`.

### Phase `W07.P14` - cross-contamination residual queue

Keep the post-commit residual test-contamination work explicit. The first guard
slice is closed, but the remaining storage, profile, application, and domain
tests still need inventory and repair before the storage state surface can be
treated as broadly hardened.

- [x] `W07.P14.S56` - Define the shared development/test database password in core settings and route database-backed storage tests through `Settings.aeat_dev_test_database_password` or `aeat.tests.secure_sql`; `src/aeat/core/config.py src/aeat/tests/secure_sql.py`.
- [x] `W07.P14.S57` - Add a guard that flags ad hoc secure-storage test password and ephemeral default-repository patterns; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [x] `W07.P14.S58` - Commit the first secure-SQL isolation helper and proof tests; `commit `177f0669a`; `src/aeat/tests/secure_sql.py src/aeat/tests/test_secure_sql.py`.
- [x] `W07.P14.S59` - Audit the remaining W04.F12 files and classify each as already isolated, repairable with `aeat.tests.secure_sql`, or requiring runtime-profile orchestration; `src/aeat/adapters src/aeat/application src/aeat/domain`.
- [x] `W07.P14.S60` - Repair the next bounded residual slice without fakes, stubs, monkeypatches, private taxpayer data, or root-database cross-contamination; `src/aeat`.
- [x] `W07.P14.S61` - Run the secure-SQL guard plus focused residual-slice tests after each repair and persist the review result; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py .vault/audit`.

## Wave `W09` - worktree coverage reconciliation

This Wave closes the tracking gap for dirty or untracked secure-storage-related artifacts. It inventories the worktree, maps each relevant artifact to an owning plan row, and records separate-plan or deferred dispositions for unrelated slices.

### Phase `W09.P16` - artifact coverage inventory

Inventory modified and untracked artifacts that touch secure storage, repair, readiness, persona testimony, and hygiene guardrails, then bind each relevant artifact to a plan row before further execution.

- [x] `W09.P16.S62` - Classify unrelated dirty slices into existing-plan, new-plan, or deferred dispositions; `.vault/plan`.
- [x] `W09.P16.S63` - Inventory dirty and untracked secure-storage-related artifacts against current plan coverage; `.vault/exec`.
- [x] `W09.P16.S64` - Persist coverage audit after plan ownership and research backing are reconciled; `.vault/audit`.

## Wave `W10` - convention regrounding audit

Reground secure-storage hardening against existing codebase conventions before further broad implementation: locale rendering, AEAT error hierarchy, logged exception handling, settings-backed environment handling, real-behavior tests, and shared enum/model reuse are audited before remediation rows execute.

### Phase `W10.P17` - codebase convention evidence review

Inspect existing implementation patterns and current secure-storage changes before assigning repairs; each audit row must cite code evidence and either open implementation rows or record a deferred disposition.

- [x] `W10.P17.S65` - Audit user-facing secure-storage error messages for tr-backed locale rendering before further repairs; `src/aeat`.
- [x] `W10.P17.S66` - Audit secure-storage exceptions for AEAT core error base-class derivation and registry coverage; `src/aeat/adapters/persistence/storage`.
- [x] `W10.P17.S67` - Audit exception swallowing and require at-least-debug logging or explicit typed degradation records; `src/aeat`.
- [x] `W10.P17.S68` - Audit secure-storage tests for tautological assertions, fake helpers, stubs, patches, skips, xfails, and mirrored business logic; `src/aeat`.
- [x] `W10.P17.S69` - Audit environment and storage-route handling for centralized Settings usage and naked env access; `src/aeat`.
- [x] `W10.P17.S70` - Audit secure-storage implementations for duplicated enums, duplicated models, and missed shared pydantic model reuse; `src/aeat`.

## Wave `W11` - convention hardening remediation

Execute only the convention repairs justified by the W10 evidence review, keeping user-facing text localized, errors registry-bound, swallowed failures observable, tests real-behavior, environment handling settings-backed, and shared models authoritative.

### Phase `W11.P18` - localized errors and exception observability

Repair secure-storage user-facing errors and exception handling only after W10 identifies concrete gaps, preserving centralized translation and typed error contracts.

- [x] `W11.P18.S71` - Repair user-facing secure-storage messages to use tr-backed locale keys and validate with aeat.locales CLI; `src/aeat`.
- [x] `W11.P18.S72` - Repair secure-storage exception classes to derive from AEAT core bases with registry-backed error codes; `src/aeat/adapters/persistence/storage`.
- [x] `W11.P18.S73` - Repair swallowed secure-storage exceptions with debug logging or explicit typed degradation surfaces; `src/aeat`.

### Phase `W11.P19` - settings tests and model reuse hardening

Repair implementation and test gaps where W10 finds naked environment access, tautological tests, or duplicated contracts instead of central Settings, shared enums, and shared pydantic models.

- [x] `W11.P19.S74` - Repair naked environment handling by routing storage and test configuration through centralized Settings helpers; `src/aeat`.
- [x] `W11.P19.S75` - Repair tautological or shortcut tests with real-behavior coverage that imports production code directly; `src/aeat`.
- [x] `W11.P19.S76` - Repair duplicated secure-storage enums and models by reusing core enums, shared models, and pydantic contracts; `src/aeat`.
- [x] `W11.P19.S77` - Add guard checks for settings-backed environment use, translation coverage, error registry binding, and test-hygiene regressions; `src/aeat`.

## Wave `W12` - active-profile StorageRuntime rollout

This Wave expands the accepted W02 runtime direction into an explicit application-wide rollout. It does not create a competing ADR. It treats the active-profile storage runtime discovery audit as the mechanical baseline and converts each discovered production storage/profile signal into a typed disposition before implementation proceeds.

Execution rule: every changed production caller must be classified as exactly one of `runtime-default`, `manifest-discovery`, `bootstrap-custody`, `test-runtime`, `plaintext-exception`, `remote-mirror`, or `retired`. Every `runtime-default` caller must receive repositories through `StorageRuntime` or a runtime-owned factory. Every retained exception must have an owning plan row, a rationale, and a closeout check.

Runtime adoption register rows must use this shape in execution notes:

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/...` | `SecureObjectRepository()` | `runtime-default` | active bucket session and route match | migrate to test runtime profile | pending |

### Affected-file rollout register

This register is intentionally monotonous. It lists every current production Python file matched by the expanded storage/profile scanner, including direct secure repositories, active-profile resolution, manifest/bucket discovery, master-key custody, SQL routing, plaintext side stores, and remote storage providers. Rows that are later proven to be false positives must still be closed with a disposition instead of silently disappearing from scope.

Current register count: `301` production candidate files.

| ID | Path | Signals | Target type | Owning row | Status |
| --- | --- | --- | --- | --- | --- |
| `AFR-001` | `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-002` | `src/aeat/adapters/inbound/borrador/_parser.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-003` | `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-004` | `src/aeat/adapters/inbound/declaracion/_parser.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-005` | `src/aeat/adapters/inbound/financial/providers/_ofx.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-006` | `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-007` | `src/aeat/adapters/inbound/justificante/_parser.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-008` | `src/aeat/adapters/inbound/justificante/_parsers/__init__.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-009` | `src/aeat/adapters/inbound/pdf/_pdfplumber.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-010` | `src/aeat/adapters/inbound/pdf/_utils.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-011` | `src/aeat/adapters/inbound/sanitizer/_errors.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-012` | `src/aeat/adapters/inbound/sanitizer/_pipeline.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-013` | `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-014` | `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` | `secure-object, active-profile, manifest-bucket, master-key, plain-file` | `runtime-default` | `W12.P21.S86` | migrated |
| `AFR-015` | `src/aeat/adapters/outbound/aeat/auth/_session_store.py` | `secure-object, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-016` | `src/aeat/adapters/outbound/aeat/browser/_factory.py` | `active-profile, manifest-bucket, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-017` | `src/aeat/adapters/outbound/aeat/browser/_site_health.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-018` | `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-019` | `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-020` | `src/aeat/adapters/outbound/aeat/sede/_censo_live.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-021` | `src/aeat/adapters/outbound/aeat/sede/_declarations.py` | `manifest-bucket, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-022` | `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-023` | `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` | `secure-object, manifest-bucket, master-key, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-024` | `src/aeat/adapters/outbound/aeat/sede/_parse.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-025` | `src/aeat/adapters/outbound/aeat/sede/_renta_web_open_safety.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-026` | `src/aeat/adapters/outbound/aeat/verify/__init__.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-027` | `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-028` | `src/aeat/adapters/outbound/google/_calc_sheets_pull.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-029` | `src/aeat/adapters/outbound/google/_errors.py` | `active-profile` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-030` | `src/aeat/adapters/outbound/google/_oauth_flow.py` | `secure-object, active-profile, manifest-bucket, master-key, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-031` | `src/aeat/adapters/outbound/google/_profile_binding.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-032` | `src/aeat/adapters/outbound/google/_records.py` | `secure-object, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-033` | `src/aeat/adapters/outbound/google/_refresh.py` | `remote-provider` | `retired` | `W12.P24.S98` | closed |
| `AFR-034` | `src/aeat/adapters/outbound/google/_session_store.py` | `secure-object, active-profile` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-035` | `src/aeat/adapters/outbound/llm/_cache.py` | `secure-object, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-036` | `src/aeat/adapters/outbound/llm/_providers/gemini.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-037` | `src/aeat/adapters/outbound/llm/_usage.py` | `secure-object, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-038` | `src/aeat/adapters/outbound/storage/__init__.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-039` | `src/aeat/adapters/outbound/storage/_errors.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-040` | `src/aeat/adapters/outbound/storage/_factory.py` | `active-profile, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-041` | `src/aeat/adapters/outbound/storage/_google_drive.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-042` | `src/aeat/adapters/outbound/storage/_local.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-043` | `src/aeat/adapters/outbound/storage/_protocol.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-044` | `src/aeat/adapters/outbound/storage/_records.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-045` | `src/aeat/adapters/persistence/profile/assets.py` | `secure-object, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-046` | `src/aeat/adapters/persistence/profile/inventory.py` | `secure-object, sql-route, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-047` | `src/aeat/adapters/persistence/storage/__init__.py` | `runtime, master-key` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-048` | `src/aeat/adapters/persistence/storage/_path_safety.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-049` | `src/aeat/adapters/persistence/storage/_rotation.py` | `master-key, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-050` | `src/aeat/adapters/persistence/storage/attachment.py` | `secure-object, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-051` | `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` | `master-key, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-052` | `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` | `master-key, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-053` | `src/aeat/adapters/persistence/storage/bucket/__init__.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-054` | `src/aeat/adapters/persistence/storage/bucket/_errors.py` | `manifest-bucket, master-key` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-055` | `src/aeat/adapters/persistence/storage/bucket/_export_header.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-056` | `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-057` | `src/aeat/adapters/persistence/storage/bucket/_layout.py` | `manifest-bucket, sql-route` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-058` | `src/aeat/adapters/persistence/storage/bucket/_lockfile.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-059` | `src/aeat/adapters/persistence/storage/bucket/_manifest.py` | `manifest-bucket, master-key, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-060` | `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-061` | `src/aeat/adapters/persistence/storage/crypto/__init__.py` | `master-key` | `runtime-default` | `W12.P20.S78` | closed |
| `AFR-062` | `src/aeat/adapters/persistence/storage/crypto/_crypto.py` | `master-key` | `runtime-default` | `W12.P20.S78` | closed |
| `AFR-063` | `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` | `secure-object, master-key, sql-route` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-064` | `src/aeat/adapters/persistence/storage/envelope/__init__.py` | `secure-bound` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-065` | `src/aeat/adapters/persistence/storage/envelope/_envelope.py` | `master-key, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-066` | `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py` | `secure-object, secure-bound, sql-route` | `runtime-default` | `W12.P21.S86` | migrated |
| `AFR-067` | `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py` | `secure-object, secure-bound, active-profile, manifest-bucket, plain-file` | `runtime-default` | `W12.P21.S86` | migrated |
| `AFR-068` | `src/aeat/adapters/persistence/storage/errors.py` | `master-key` | `runtime-default` | `W12.P20.S78` | migrated |
| `AFR-069` | `src/aeat/adapters/persistence/storage/master_key/__init__.py` | `master-key` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-070` | `src/aeat/adapters/persistence/storage/master_key/_active_session.py` | `manifest-bucket, master-key` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-071` | `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` | `manifest-bucket, master-key, sql-route, plain-file` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-072` | `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py` | `manifest-bucket` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-073` | `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py` | `manifest-bucket, master-key` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-074` | `src/aeat/adapters/persistence/storage/master_key/_kdf.py` | `master-key` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-075` | `src/aeat/adapters/persistence/storage/master_key/_master_key.py` | `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-076` | `src/aeat/adapters/persistence/storage/master_key/_recovery.py` | `master-key, plain-file` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-077` | `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py` | `manifest-bucket, master-key, plain-file` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-078` | `src/aeat/adapters/persistence/storage/master_key/test_no_classvar_state.py` | `master-key, plain-file` | `retired` | `W12.P22.S89` | closed |
| `AFR-079` | `src/aeat/adapters/persistence/storage/master_key/_zeroise.py` | `master-key` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-080` | `src/aeat/adapters/persistence/storage/runtime.py` | `secure-object, runtime, active-profile, manifest-bucket, master-key, sql-route` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-081` | `src/aeat/adapters/persistence/storage/runtime_repository.py` | `secure-object, runtime, manifest-bucket` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-082` | `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py` | `master-key, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-083` | `src/aeat/adapters/persistence/storage/sql/__init__.py` | `secure-object` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-084` | `src/aeat/adapters/persistence/storage/sql/_orm.py` | `secure-object` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-085` | `src/aeat/adapters/persistence/storage/sql/engine.py` | `sql-route, plain-file` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-086` | `src/aeat/adapters/persistence/storage/sql/secure_objects.py` | `secure-object, manifest-bucket, master-key, sql-route, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-087` | `src/aeat/adapters/persistence/storage/sql/session.py` | `sql-route` | `runtime-default` | `W12.P21.S86` | closed |
| `AFR-088` | `src/aeat/application/aggregation/_iva_ledger.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-089` | `src/aeat/application/aggregation/_modelo_bindings.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-090` | `src/aeat/application/aggregation/_renta_ledger.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-091` | `src/aeat/application/aggregation/_source_mesh.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-092` | `src/aeat/application/aggregation/_source_profile.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-093` | `src/aeat/application/auth/_acquisition_lock.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-094` | `src/aeat/application/auth/_apoderado.py` | `secure-object, secure-bound, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-095` | `src/aeat/application/auth/_diagnostics.py` | `secure-object, active-profile` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-096` | `src/aeat/application/auth/_operator.py` | `secure-object, active-profile, manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-097` | `src/aeat/application/auth/_sessions.py` | `active-profile, manifest-bucket, master-key, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-098` | `src/aeat/application/calculations/_iva_compensation_history.py` | `secure-bound` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-099` | `src/aeat/application/calculations/_observations_repository.py` | `secure-object, secure-bound` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-100` | `src/aeat/application/config_reset.py` | `secure-object, manifest-bucket, sql-route` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-101` | `src/aeat/application/diagnostics.py` | `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-102` | `src/aeat/application/evidence/_models.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-103` | `src/aeat/application/evidence/_service.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-104` | `src/aeat/application/export/_tabular.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-105` | `src/aeat/application/filing/__init__.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-106` | `src/aeat/application/filing/_history_repository.py` | `secure-object, secure-bound, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-107` | `src/aeat/application/filing/_review.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-108` | `src/aeat/application/filing/_runtime_repository.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-109` | `src/aeat/application/filing/_testing_registry.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-110` | `src/aeat/application/filing/runtime.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-111` | `src/aeat/application/inventory/_service.py` | `secure-object, secure-bound, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-112` | `src/aeat/application/invoices/_importing.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-113` | `src/aeat/application/invoices/_linking.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-114` | `src/aeat/application/invoices/_queries.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-115` | `src/aeat/application/invoices/_reconciliation.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-116` | `src/aeat/application/invoices/_source_resolver.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-117` | `src/aeat/application/ledger/_actions.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-118` | `src/aeat/application/ledger/_business_operation_invoice.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-119` | `src/aeat/application/ledger/_evidence.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-120` | `src/aeat/application/ledger/_models.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-121` | `src/aeat/application/ledger/_preflight.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-122` | `src/aeat/application/ledger/_ratios.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-123` | `src/aeat/application/live/__init__.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-124` | `src/aeat/application/live/_borrador_100.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-125` | `src/aeat/application/live/_censo.py` | `secure-object, manifest-bucket, sql-route, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-126` | `src/aeat/application/live/_expedientes.py` | `secure-object, manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-127` | `src/aeat/application/live/_notifications.py` | `secure-object, manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-128` | `src/aeat/application/live/_snapshot_base.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-129` | `src/aeat/application/live/_verify.py` | `secure-object, manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-130` | `src/aeat/application/modelo/__init__.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-131` | `src/aeat/application/modelo/_actions.py` | `secure-object, manifest-bucket, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-132` | `src/aeat/application/modelo/_binding_readiness.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-133` | `src/aeat/application/modelo/_borrador_binding.py` | `secure-object, manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-134` | `src/aeat/application/modelo/_export.py` | `active-profile, manifest-bucket, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-135` | `src/aeat/application/modelo/_history.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-136` | `src/aeat/application/modelo/_profile_binding.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-137` | `src/aeat/application/modelo/_reconcile.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S85` | migrated |
| `AFR-138` | `src/aeat/application/operator_surface/_contract.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-139` | `src/aeat/application/operator_surface/_crud_contract.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-140` | `src/aeat/application/operator_surface/_help.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-141` | `src/aeat/application/operator_surface/_models.py` | `active-profile` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-142` | `src/aeat/application/overview/__init__.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-143` | `src/aeat/application/registry/__init__.py` | `secure-object, plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-144` | `src/aeat/application/registry/_corpus.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-145` | `src/aeat/application/repair_integrity.py` | `secure-object, secure-bound, active-profile, manifest-bucket, master-key` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-146` | `src/aeat/application/review/_adapters.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-147` | `src/aeat/application/review/_aggregator.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-148` | `src/aeat/application/review/_edit.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-149` | `src/aeat/application/review/_filter.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-150` | `src/aeat/application/review/_operator.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-151` | `src/aeat/application/setup/_contracts.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-152` | `src/aeat/application/setup/_service.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-153` | `src/aeat/application/state_projection.py` | `runtime, active-profile, manifest-bucket, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-154` | `src/aeat/application/storage/calc_sheets/_engine.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-155` | `src/aeat/application/storage/calc_sheets/_layout.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-156` | `src/aeat/application/storage/calc_sheets/_parity_harness.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-157` | `src/aeat/application/storage/calc_sheets/_records.py` | `secure-object, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-158` | `src/aeat/application/storage/calc_sheets/_translator.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-159` | `src/aeat/application/topics/__init__.py` | `plain-file` | `retired` | `W12.P24.S96` | closed |
| `AFR-160` | `src/aeat/application/user_profile/__init__.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-161` | `src/aeat/application/user_profile/_aggregate.py` | `active-profile, manifest-bucket, sql-route, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-162` | `src/aeat/application/user_profile/_censo_sync.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-163` | `src/aeat/application/user_profile/_integrity.py` | `manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-164` | `src/aeat/application/user_profile/_language_resolver.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-165` | `src/aeat/application/user_profile/_lifecycle.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-166` | `src/aeat/application/user_profile/_orchestration.py` | `secure-object, active-profile, manifest-bucket, sql-route, plain-file` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-167` | `src/aeat/application/user_profile/_profile_repository.py` | `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-168` | `src/aeat/application/user_profile/_repository.py` | `secure-object, runtime, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-169` | `src/aeat/application/user_profile/_testing.py` | `secure-object, active-profile` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-170` | `src/aeat/application/verification/_verify.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-171` | `src/aeat/application/wizard/_commands.py` | `active-profile, manifest-bucket, master-key` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-172` | `src/aeat/application/wizard/_persistence.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-173` | `src/aeat/application/wizard/_prompter.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-174` | `src/aeat/application/wizard/_status.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-175` | `src/aeat/application/wizard/_translations.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-176` | `src/aeat/application/wizard/_widgets.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-177` | `src/aeat/application/workflow/__init__.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-178` | `src/aeat/application/workflow/_errors.py` | `active-profile, manifest-bucket, master-key` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-179` | `src/aeat/application/workflow/_events.py` | `manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-180` | `src/aeat/application/workflow/_models.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-181` | `src/aeat/application/workflow/_persistence.py` | `secure-object, runtime, active-profile, manifest-bucket, master-key, sql-route` | `runtime-default` | `W12.P21.S85` | migrated |
| `AFR-182` | `src/aeat/application/workflow/_profile_bucket_scan.py` | `manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-183` | `src/aeat/application/workflow/_profile_health.py` | `active-profile, manifest-bucket, master-key, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-184` | `src/aeat/core/_bucket_pointer.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-185` | `src/aeat/core/_bucket_pointer_io.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-186` | `src/aeat/core/_toml.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-187` | `src/aeat/core/access_gate/__init__.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-188` | `src/aeat/core/config.py` | `active-profile, manifest-bucket, master-key, sql-route, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-189` | `src/aeat/core/corpus_manifest/__init__.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-190` | `src/aeat/core/env_io.py` | `master-key, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-191` | `src/aeat/core/errors/registry/_adapters.py` | `master-key` | `runtime-default` | `W12.P20.S78` | closed |
| `AFR-192` | `src/aeat/core/errors/registry/_application.py` | `active-profile` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-193` | `src/aeat/core/errors/registry/_core.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-194` | `src/aeat/core/external_constants.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-195` | `src/aeat/core/file_permissions.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-196` | `src/aeat/core/i18n/_render.py` | `active-profile, manifest-bucket, sql-route, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-197` | `src/aeat/core/locks.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-198` | `src/aeat/core/logging.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-199` | `src/aeat/core/observability/__init__.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-200` | `src/aeat/core/observability/_context.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-201` | `src/aeat/core/observability/_errors.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-202` | `src/aeat/core/observability/_fingerprint.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-203` | `src/aeat/core/observability/_models.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-204` | `src/aeat/core/observability/_recorder.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-205` | `src/aeat/core/observability/_sink.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-206` | `src/aeat/core/observability/_store.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-207` | `src/aeat/core/output_rendering.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-208` | `src/aeat/core/paths.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-209` | `src/aeat/core/resources/_boundary.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-210` | `src/aeat/core/resources/_repos/legal_parameters.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-211` | `src/aeat/core/resources/_repos/modelos.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-212` | `src/aeat/diagnostics/__main__.py` | `secure-object` | `runtime-default` | `W12.P21.S83` | closed |
| `AFR-213` | `src/aeat/diagnostics/profile.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-214` | `src/aeat/domain/_secure_storage_runtime.py` | `secure-object, runtime, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-215` | `src/aeat/domain/attachments/_models.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-216` | `src/aeat/domain/auth/apoderamientos/_catalogue.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-217` | `src/aeat/domain/buckets/__init__.py` | `secure-object` | `runtime-default` | `W12.P21.S83` | closed |
| `AFR-218` | `src/aeat/domain/buckets/_event.py` | `manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-219` | `src/aeat/domain/buckets/_event_repository.py` | `secure-object, runtime, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S83` | closed |
| `AFR-220` | `src/aeat/domain/calculations/registry/_bindings.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-221` | `src/aeat/domain/calculations/registry/_export_parse.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-222` | `src/aeat/domain/calculations/registry/_formula_runtime.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-223` | `src/aeat/domain/calculations/registry/_legal.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-224` | `src/aeat/domain/calculations/registry/_loader.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-225` | `src/aeat/domain/calculations/registry/_parity_tapes.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-226` | `src/aeat/domain/calculations/registry/_record_design.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-227` | `src/aeat/domain/calculations/registry/_schema.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-228` | `src/aeat/domain/calculations/registry/_snapshot.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-229` | `src/aeat/domain/calculations/registry/_sources.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-230` | `src/aeat/domain/calculations/registry/_validate_evidence.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-231` | `src/aeat/domain/calculations/registry/_workbook_parity.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-232` | `src/aeat/domain/categories/_registry.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-233` | `src/aeat/domain/deadlines/_engine.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-234` | `src/aeat/domain/deadlines/_festivos.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-235` | `src/aeat/domain/deadlines/_recargo.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-236` | `src/aeat/domain/filing/_complementaria_repository.py` | `secure-object, manifest-bucket, plain-file` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-237` | `src/aeat/domain/filing/_repository.py` | `secure-object, secure-bound, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-238` | `src/aeat/domain/filing/_runtime_repository.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-239` | `src/aeat/domain/fincas/_imputacion_parameters.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-240` | `src/aeat/domain/invoices/_models.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-241` | `src/aeat/domain/invoices/_repository.py` | `secure-object, runtime, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-242` | `src/aeat/domain/iva/_catalogue.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-243` | `src/aeat/domain/iva/_rates.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-244` | `src/aeat/domain/iva/_recargo_equivalencia.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-245` | `src/aeat/domain/iva/_schema.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-246` | `src/aeat/domain/justificante/_repository.py` | `secure-bound` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-247` | `src/aeat/domain/manuals/_fetch.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-248` | `src/aeat/domain/manuals/_loader.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-249` | `src/aeat/domain/manuals/_verify.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-250` | `src/aeat/domain/manuals/errors.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-251` | `src/aeat/domain/modelos/_calculation_repository.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-252` | `src/aeat/domain/modelos/_filing_record.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-253` | `src/aeat/domain/modelos/_filing_repository.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-254` | `src/aeat/domain/modelos/_repository.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-255` | `src/aeat/domain/modelos/_runtime_repository.py` | `secure-object, active-profile, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-256` | `src/aeat/domain/modelos/_verification_repository.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-257` | `src/aeat/domain/modelos/_work_unit.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-258` | `src/aeat/domain/normatives/_loader.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-259` | `src/aeat/domain/renta/_substrate.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-260` | `src/aeat/domain/submission/_models.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-261` | `src/aeat/domain/submission/_preflight.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-262` | `src/aeat/domain/submission/_protocols.py` | `plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-263` | `src/aeat/domain/submission/_repository.py` | `secure-bound` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-264` | `src/aeat/domain/transactions/_errors.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-265` | `src/aeat/domain/transactions/_models.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-266` | `src/aeat/domain/transactions/_raw_transaction.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-267` | `src/aeat/domain/transactions/_repository.py` | `secure-object, runtime, manifest-bucket` | `runtime-default` | `W12.P21.S84` | closed |
| `AFR-268` | `src/aeat/domain/usage_ratios/_model.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-269` | `src/aeat/domain/usage_ratios/_service.py` | `secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S84` | migrated |
| `AFR-270` | `src/aeat/domain/user_profile/_loader.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-271` | `src/aeat/domain/user_profile/_values.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-272` | `src/aeat/entrypoints/cli/__init__.py` | `active-profile, manifest-bucket, master-key, sql-route, plain-file` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-273` | `src/aeat/entrypoints/cli/_app_live.py` | `secure-object, active-profile, manifest-bucket, plain-file` | `runtime-default` | `W12.P21.S83` | closed |
| `AFR-274` | `src/aeat/entrypoints/cli/_bootstrap_exempt.py` | `master-key` | `runtime-default` | `W12.P20.S78` | closed |
| `AFR-275` | `src/aeat/entrypoints/cli/_common.py` | `active-profile, manifest-bucket, sql-route` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-276` | `src/aeat/entrypoints/cli/_config/__init__.py` | `secure-object, active-profile, manifest-bucket, master-key, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-277` | `src/aeat/entrypoints/cli/_config/_google.py` | `secure-object, active-profile, plain-file, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-278` | `src/aeat/entrypoints/cli/_config/_profile_censo.py` | `active-profile, manifest-bucket` | `bootstrap-custody` | `W12.P22.S89` | closed |
| `AFR-279` | `src/aeat/entrypoints/cli/_errors.py` | `master-key` | `runtime-default` | `W12.P20.S78` | closed |
| `AFR-280` | `src/aeat/entrypoints/cli/_ledger.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-281` | `src/aeat/entrypoints/cli/_modelo.py` | `active-profile, manifest-bucket, sql-route, plain-file` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-282` | `src/aeat/entrypoints/cli/_modelo_payloads.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-283` | `src/aeat/entrypoints/cli/_overview.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-284` | `src/aeat/entrypoints/cli/_overview_rendering.py` | `active-profile` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-285` | `src/aeat/entrypoints/cli/_review.py` | `manifest-bucket` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-286` | `src/aeat/entrypoints/cli/_review_payloads.py` | `manifest-bucket, remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-287` | `src/aeat/entrypoints/cli/_root_landing.py` | `active-profile` | `manifest-discovery` | `W12.P22.S90` | closed |
| `AFR-288` | `src/aeat/entrypoints/cli/_schemas.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-289` | `src/aeat/entrypoints/cli/_tty.py` | `remote-provider` | `remote-mirror` | `W12.P24.S98` | closed |
| `AFR-290` | `src/aeat/entrypoints/cli/registry.py` | `plain-file, secure-object, manifest-bucket` | `runtime-default` | `W12.P21.S85` | closed |
| `AFR-291` | `src/aeat/locales/_ast_scanner.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-292` | `src/aeat/locales/cli.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-293` | `src/aeat/locales/manager.py` | `plain-file` | `plaintext-exception` | `W12.P24.S96` | closed |
| `AFR-294` | `src/aeat/application/modelo/_projection.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W18.P38.S442` | closed |
| `AFR-295` | `src/aeat/application/modelo/_selectors.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W18.P38.S443` | closed |
| `AFR-296` | `src/aeat/application/modelo/_work_addressing.py` | `active-profile, manifest-bucket` | `manifest-discovery` | `W18.P38.S444` | closed |
| `AFR-297` | `src/aeat/application/modelo/_work_create_policy.py` | `active-profile, plain-file` | `manifest-discovery` | `W18.P38.S445` | closed |
| `AFR-298` | `src/aeat/application/modelo/_work_plazo.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W18.P38.S446` | closed |
| `AFR-299` | `src/aeat/application/modelo/_iva_wallet_seed.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W18.P38.S447` | closed |
| `AFR-300` | `src/aeat/entrypoints/cli/_modelo_projection_cli.py` | `active-profile, plain-file` | `manifest-discovery` | `W18.P38.S448` | closed |
| `AFR-301` | `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py` | `active-profile, manifest-bucket, plain-file` | `manifest-discovery` | `W18.P38.S449` | closed |

### Phase `W12.P20` - adoption register and classification

Turn the audit inventory into a repeatable rollout register so implementation agents do not rediscover or re-scope the surface independently.

- [x] `W12.P20.S78` - Convert the active-profile runtime discovery audit production index into a runtime adoption register grouped by adapter, application, domain, core, and CLI ownership; `.vault/exec`.
- [x] `W12.P20.S79` - Classify each direct `SecureObjectRepository()` and `SecureBoundRepository` default as `runtime-default`, `bootstrap-custody`, `test-runtime`, or `retired`; `src/aeat`.
- [x] `W12.P20.S80` - Classify each pointer, manifest, and bucket scan caller as `manifest-discovery`, `bootstrap-custody`, or `runtime-default`; `src/aeat`.
- [x] `W12.P20.S81` - Classify each SQL route, active-profile, and master-key session caller as runtime policy, bootstrap policy, or test-only setup; `src/aeat`.
- [x] `W12.P20.S82` - Persist classification closeout with unresolved exceptions and explicit owner rows before migration tasks start; `.vault/audit`.

### Phase `W12.P21` - runtime default repository migration

Move production repositories away from direct physical-store construction while preserving explicit constructor injection for real-behavior tests and controlled bootstrap paths.

- [x] `W12.P21.S83` - Migrate workflow state and bucket-event repositories to runtime-owned secure-object factories; `src/aeat`.
- [x] `W12.P21.S84` - Migrate transaction, invoice, filing, submission, justificante, and modelo repositories to runtime-owned secure-bound or secure-object factories; `src/aeat/domain`.
- [x] `W12.P21.S85` - Migrate ledger, filing history, modelo reconciliation, calculation observation, usage-ratio, and calc-sheet repositories to runtime-owned defaults; `src/aeat/application`.
- [x] `W12.P21.S86` - Migrate auth, AEAT observation, Google OAuth/session, LLM cache/usage, and outbound adapter repositories to runtime-owned defaults or classified remote-mirror paths; `src/aeat/adapters`.
- [x] `W12.P21.S87` - Add focused real-behavior tests for each migrated repository family proving active profile routing, route mismatch refusal, missing-session refusal, and isolated test profile writes; `src/aeat`.

### Phase `W12.P22` - CLI and profile bootstrap boundary

Keep the CLI as the operator-command surface while moving storage readiness and write-policy decisions into runtime/backend services.

- [x] `W12.P22.S88` - Replace CLI guarded write-verb route policy with a runtime readiness/write-policy query while preserving bootstrap exemptions; `src/aeat/entrypoints/cli`.
- [x] `W12.P22.S89` - Move profile create, switch, delete, and logout storage spans behind named runtime or profile-lifecycle operations without bypassing `ProfileRepository`; `src/aeat`.
- [x] `W12.P22.S90` - Preserve manifest scanning as a read-only profile discovery adapter separate from encrypted runtime attachment; `src/aeat/application`.
- [x] `W12.P22.S91` - Add CLI regression tests for bootstrap, explicit profile selection, environment selection, pointer selection, root fallback refusal, and explicit route refusal through backend runtime policy; `src/aeat/entrypoints/cli`.

### Phase `W12.P23` - first-class test profile runtime

Replace ad hoc database-route sandboxing with a sanctioned real runtime profile path so tests exercise the same storage attachment contract as production.

- [x] `W12.P23.S92` - Add a test runtime profile helper that creates a real isolated profile bucket, SQLite database, bucket manifest, master-key session, and runtime-bound secure-object repository; `src/aeat/tests`.
- [x] `W12.P23.S93` - Migrate explicit `aeat_database_url`, `AEAT_DATABASE_URL`, and injected-engine test setup to the test runtime helper except in route-classification and refusal tests; `src/aeat`.
- [x] `W12.P23.S94` - Add guard coverage that rejects new production raw secure-object construction and new unapproved route-based test setup; `src/aeat/adapters/persistence/storage`.
- [x] `W12.P23.S95` - Persist a test-isolation closeout audit listing remaining approved explicit-route tests and their owning refusal behavior; `.vault/audit`.

### Phase `W12.P24` - side-store and mirror disposition

Classify bucket-local plaintext stores and remote provider surfaces so the runtime rollout does not leave sensitive data in parallel backends.

- [x] `W12.P24.S96` - Classify evidence, inventory, ledger evidence, business-operation invoice, live notification, live verification, expedientes, and snapshot file stores as secure-object migration, export-only, rebuildable cache, or accepted plaintext exception; `src/aeat/application`.
- [x] `W12.P24.S97` - Migrate sensitive bucket-local side stores to runtime-created secure-object repositories or persist accepted exception ADR coverage before retaining them; `src/aeat/application`.
- [x] `W12.P24.S98` - Bind outbound storage providers to encrypted mirror semantics with runtime-derived profile identity and namespace policy; `src/aeat/adapters/outbound/storage`.
- [x] `W12.P24.S99` - Add real-behavior tests proving retained file stores do not become alternate sensitive persistence backends; `src/aeat`.

### Phase `W12.P25` - rollout closeout gates

Close the runtime rollout only after mechanical checks prove the application no longer depends on competing active-profile storage APIs.

- [x] `W12.P25.S100` - Run the mechanical scanner from the active-profile runtime audit and persist a before/after delta for production and test signals; `.vault/audit`.
- [x] `W12.P25.S101` - Run focused storage, profile lifecycle, CLI, workflow, domain repository, outbound adapter, and test-runtime gates after runtime migration; `src/aeat`.
- [x] `W12.P25.S102` - Persist a final runtime rollout review proving direct constructors, explicit-route tests, manifest discovery, bootstrap custody, side-store exceptions, and remote mirrors each have one accepted disposition; `.vault/audit`.

### Phase `W12.P26` - affected-file CLI closure ledger

These rows duplicate the `AFR-*` register as vaultspec plan steps so `vaultspec-core vault plan status`, `vaultspec-core vault plan check`, and `vaultspec-core vault plan step check` can track file-level closure mechanically. Do not close a step until the matching `AFR-*` table row has a final disposition and the owning implementation row has either migrated, retained, or explicitly rejected the file.

- [x] `W12.P26.S103` - Close `AFR-001` for `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`.
- [x] `W12.P26.S104` - Close `AFR-002` for `src/aeat/adapters/inbound/borrador/_parser.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/borrador/_parser.py`.
- [x] `W12.P26.S105` - Close `AFR-003` for `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`.
- [x] `W12.P26.S106` - Close `AFR-004` for `src/aeat/adapters/inbound/declaracion/_parser.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W12.P26.S107` - Close `AFR-005` for `src/aeat/adapters/inbound/financial/providers/_ofx.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/financial/providers/_ofx.py`.
- [x] `W12.P26.S108` - Close `AFR-006` for `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py`.
- [x] `W12.P26.S109` - Close `AFR-007` for `src/aeat/adapters/inbound/justificante/_parser.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/justificante/_parser.py`.
- [x] `W12.P26.S110` - Close `AFR-008` for `src/aeat/adapters/inbound/justificante/_parsers/__init__.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/justificante/_parsers/__init__.py`.
- [x] `W12.P26.S111` - Close `AFR-009` for `src/aeat/adapters/inbound/pdf/_pdfplumber.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [x] `W12.P26.S112` - Close `AFR-010` for `src/aeat/adapters/inbound/pdf/_utils.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/inbound/pdf/_utils.py`.
- [x] `W12.P26.S113` - Close `AFR-011` for `src/aeat/adapters/inbound/sanitizer/_errors.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/inbound/sanitizer/_errors.py`.
- [x] `W12.P26.S114` - Close `AFR-012` for `src/aeat/adapters/inbound/sanitizer/_pipeline.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/inbound/sanitizer/_pipeline.py`.
- [x] `W12.P26.S115` - Close `AFR-013` for `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W12.P26.S116` - Close `AFR-014` for `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` with signals `secure-object, active-profile, manifest-bucket, master-key, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W12.P26.S117` - Close `AFR-015` for `src/aeat/adapters/outbound/aeat/auth/_session_store.py` with signals `secure-object, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/outbound/aeat/auth/_session_store.py`.
- [x] `W12.P26.S118` - Close `AFR-016` for `src/aeat/adapters/outbound/aeat/browser/_factory.py` with signals `active-profile, manifest-bucket, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/browser/_factory.py`.
- [x] `W12.P26.S119` - Close `AFR-017` for `src/aeat/adapters/outbound/aeat/browser/_site_health.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/browser/_site_health.py`.
- [x] `W12.P26.S120` - Close `AFR-018` for `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`.
- [x] `W12.P26.S121` - Close `AFR-019` for `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.
- [x] `W12.P26.S122` - Close `AFR-020` for `src/aeat/adapters/outbound/aeat/sede/_censo_live.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [x] `W12.P26.S123` - Close `AFR-021` for `src/aeat/adapters/outbound/aeat/sede/_declarations.py` with signals `manifest-bucket, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W12.P26.S124` - Close `AFR-022` for `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`.
- [x] `W12.P26.S125` - Close `AFR-023` for `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` with signals `secure-object, manifest-bucket, master-key, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [x] `W12.P26.S126` - Close `AFR-024` for `src/aeat/adapters/outbound/aeat/sede/_parse.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/outbound/aeat/sede/_parse.py`.
- [x] `W12.P26.S127` - Close `AFR-025` for `src/aeat/adapters/outbound/aeat/sede/_renta_web_open_safety.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/sede/_renta_web_open_safety.py`.
- [x] `W12.P26.S128` - Close `AFR-026` for `src/aeat/adapters/outbound/aeat/verify/__init__.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/aeat/verify/__init__.py`.
- [x] `W12.P26.S129` - Close `AFR-027` for `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [x] `W12.P26.S130` - Close `AFR-028` for `src/aeat/adapters/outbound/google/_calc_sheets_pull.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [x] `W12.P26.S131` - Close `AFR-029` for `src/aeat/adapters/outbound/google/_errors.py` with signals `active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/outbound/google/_errors.py`.
- [x] `W12.P26.S132` - Close `AFR-030` for `src/aeat/adapters/outbound/google/_oauth_flow.py` with signals `secure-object, active-profile, manifest-bucket, master-key, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/google/_oauth_flow.py`.
- [x] `W12.P26.S133` - Close `AFR-031` for `src/aeat/adapters/outbound/google/_profile_binding.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [x] `W12.P26.S134` - Close `AFR-032` for `src/aeat/adapters/outbound/google/_records.py` with signals `secure-object, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/google/_records.py`.
- [x] `W12.P26.S135` - Close stale `AFR-033` for absent `src/aeat/adapters/outbound/google/_refresh.py` with signals `remote-provider`, target `retired`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/google/_refresh.py`.
- [x] `W12.P26.S136` - Close `AFR-034` for `src/aeat/adapters/outbound/google/_session_store.py` with signals `secure-object, active-profile`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/outbound/google/_session_store.py`.
- [x] `W12.P26.S137` - Close `AFR-035` for `src/aeat/adapters/outbound/llm/_cache.py` with signals `secure-object, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/llm/_cache.py`.
- [x] `W12.P26.S138` - Close `AFR-036` for `src/aeat/adapters/outbound/llm/_providers/gemini.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/llm/_providers/gemini.py`.
- [x] `W12.P26.S139` - Close `AFR-037` for `src/aeat/adapters/outbound/llm/_usage.py` with signals `secure-object, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/outbound/llm/_usage.py`.
- [x] `W12.P26.S140` - Close `AFR-038` for `src/aeat/adapters/outbound/storage/__init__.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/__init__.py`.
- [x] `W12.P26.S141` - Close `AFR-039` for `src/aeat/adapters/outbound/storage/_errors.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_errors.py`.
- [x] `W12.P26.S142` - Close `AFR-040` for `src/aeat/adapters/outbound/storage/_factory.py` with signals `active-profile, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_factory.py`.
- [x] `W12.P26.S143` - Close `AFR-041` for `src/aeat/adapters/outbound/storage/_google_drive.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_google_drive.py`.
- [x] `W12.P26.S144` - Close `AFR-042` for `src/aeat/adapters/outbound/storage/_local.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_local.py`.
- [x] `W12.P26.S145` - Close `AFR-043` for `src/aeat/adapters/outbound/storage/_protocol.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_protocol.py`.
- [x] `W12.P26.S146` - Close `AFR-044` for `src/aeat/adapters/outbound/storage/_records.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/outbound/storage/_records.py`.
- [x] `W12.P26.S147` - Close `AFR-045` for `src/aeat/adapters/persistence/profile/assets.py` with signals `secure-object, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/persistence/profile/assets.py`.
- [x] `W12.P26.S148` - Close `AFR-046` for `src/aeat/adapters/persistence/profile/inventory.py` with signals `secure-object, sql-route, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/profile/inventory.py`.
- [x] `W12.P26.S149` - Close `AFR-047` for `src/aeat/adapters/persistence/storage/__init__.py` with signals `runtime, master-key`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/__init__.py`.
- [x] `W12.P26.S150` - Close `AFR-048` for `src/aeat/adapters/persistence/storage/_path_safety.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/persistence/storage/_path_safety.py`.
- [x] `W12.P26.S151` - Close `AFR-049` for `src/aeat/adapters/persistence/storage/_rotation.py` with signals `master-key, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/persistence/storage/_rotation.py`.
- [x] `W12.P26.S152` - Close `AFR-050` for `src/aeat/adapters/persistence/storage/attachment.py` with signals `secure-object, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/attachment.py`.
- [x] `W12.P26.S153` - Close `AFR-051` for `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` with signals `master-key, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`.
- [x] `W12.P26.S154` - Close `AFR-052` for `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` with signals `master-key, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py`.
- [x] `W12.P26.S155` - Close `AFR-053` for `src/aeat/adapters/persistence/storage/bucket/__init__.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/__init__.py`.
- [x] `W12.P26.S156` - Close `AFR-054` for `src/aeat/adapters/persistence/storage/bucket/_errors.py` with signals `manifest-bucket, master-key`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_errors.py`.
- [x] `W12.P26.S157` - Close `AFR-055` for `src/aeat/adapters/persistence/storage/bucket/_export_header.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `W12.P26.S158` - Close `AFR-056` for `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`.
- [x] `W12.P26.S159` - Close `AFR-057` for `src/aeat/adapters/persistence/storage/bucket/_layout.py` with signals `manifest-bucket, sql-route`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_layout.py`.
- [x] `W12.P26.S160` - Close `AFR-058` for `src/aeat/adapters/persistence/storage/bucket/_lockfile.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`.
- [x] `W12.P26.S161` - Close `AFR-059` for `src/aeat/adapters/persistence/storage/bucket/_manifest.py` with signals `manifest-bucket, master-key, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/persistence/storage/bucket/_manifest.py`.
- [x] `W12.P26.S162` - Close `AFR-060` for `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [x] `W12.P26.S163` - Close `AFR-061` for `src/aeat/adapters/persistence/storage/crypto/__init__.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/adapters/persistence/storage/crypto/__init__.py`.
- [x] `W12.P26.S164` - Close `AFR-062` for `src/aeat/adapters/persistence/storage/crypto/_crypto.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/adapters/persistence/storage/crypto/_crypto.py`.
- [x] `W12.P26.S165` - Close `AFR-063` for `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` with signals `secure-object, master-key, sql-route`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [x] `W12.P26.S166` - Close `AFR-064` for `src/aeat/adapters/persistence/storage/envelope/__init__.py` with signals `secure-bound`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/envelope/__init__.py`.
- [x] `W12.P26.S167` - Close `AFR-065` for `src/aeat/adapters/persistence/storage/envelope/_envelope.py` with signals `master-key, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/adapters/persistence/storage/envelope/_envelope.py`.
- [x] `W12.P26.S168` - Close `AFR-066` for `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py` with signals `secure-object, secure-bound, sql-route`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py`.
- [x] `W12.P26.S169` - Close `AFR-067` for `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py` with signals `secure-object, secure-bound, active-profile, manifest-bucket, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W12.P26.S170` - Close `AFR-068` for `src/aeat/adapters/persistence/storage/errors.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/adapters/persistence/storage/errors.py`.
- [x] `W12.P26.S171` - Close `AFR-069` for `src/aeat/adapters/persistence/storage/master_key/__init__.py` with signals `master-key`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/__init__.py`.
- [x] `W12.P26.S172` - Close `AFR-070` for `src/aeat/adapters/persistence/storage/master_key/_active_session.py` with signals `manifest-bucket, master-key`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_active_session.py`.
- [x] `W12.P26.S173` - Close `AFR-071` for `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` with signals `manifest-bucket, master-key, sql-route, plain-file`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
- [x] `W12.P26.S174` - Close `AFR-072` for `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py` with signals `manifest-bucket`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`.
- [x] `W12.P26.S175` - Close `AFR-073` for `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py` with signals `manifest-bucket, master-key`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py`.
- [x] `W12.P26.S176` - Close `AFR-074` for `src/aeat/adapters/persistence/storage/master_key/_kdf.py` with signals `master-key`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_kdf.py`.
- [x] `W12.P26.S177` - Close `AFR-075` for `src/aeat/adapters/persistence/storage/master_key/_master_key.py` with signals `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W12.P26.S178` - Close `AFR-076` for `src/aeat/adapters/persistence/storage/master_key/_recovery.py` with signals `master-key, plain-file`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W12.P26.S179` - Close `AFR-077` for `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py` with signals `manifest-bucket, master-key, plain-file`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W12.P26.S180` - Close stale duplicate `AFR-078` for retired no-classvar guard; `src/aeat/adapters/persistence/storage/master_key/test_no_classvar_state.py`.
- [x] `W12.P26.S181` - Close `AFR-079` for `src/aeat/adapters/persistence/storage/master_key/_zeroise.py` with signals `master-key`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/adapters/persistence/storage/master_key/_zeroise.py`.
- [x] `W12.P26.S182` - Close `AFR-080` for runtime readiness, localized blank-bucket validation, runtime tests, and convention-guard enrollment; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `W12.P26.S183` - Close `AFR-081` for `src/aeat/adapters/persistence/storage/runtime_repository.py` with signals `secure-object, runtime, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/runtime_repository.py`.
- [x] `W12.P26.S184` - Close `AFR-082` for `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py` with signals `master-key, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`.
- [x] `W12.P26.S185` - Close `AFR-083` for `src/aeat/adapters/persistence/storage/sql/__init__.py` with signals `secure-object`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/sql/__init__.py`.
- [x] `W12.P26.S186` - Close `AFR-084` for `src/aeat/adapters/persistence/storage/sql/_orm.py` with signals `secure-object`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W12.P26.S187` - Close `AFR-085` for `src/aeat/adapters/persistence/storage/sql/engine.py` with signals `sql-route, plain-file`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/sql/engine.py`.
- [x] `W12.P26.S188` - Close `AFR-086` for `src/aeat/adapters/persistence/storage/sql/secure_objects.py` with signals `secure-object, manifest-bucket, master-key, sql-route, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `W12.P26.S189` - Close `AFR-087` for `src/aeat/adapters/persistence/storage/sql/session.py` with signals `sql-route`, target `runtime-default`, and owner `W12.P21.S86`; `src/aeat/adapters/persistence/storage/sql/session.py`.
- [x] `W12.P26.S190` - Close `AFR-088` for `src/aeat/application/aggregation/_iva_ledger.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W12.P26.S191` - Close `AFR-089` for `src/aeat/application/aggregation/_modelo_bindings.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `W12.P26.S192` - Close `AFR-090` for `src/aeat/application/aggregation/_renta_ledger.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `W12.P26.S193` - Close `AFR-091` for `src/aeat/application/aggregation/_source_mesh.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W12.P26.S194` - Close `AFR-092` for `src/aeat/application/aggregation/_source_profile.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/aggregation/_source_profile.py`.
- [x] `W12.P26.S195` - Close `AFR-093` for `src/aeat/application/auth/_acquisition_lock.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/auth/_acquisition_lock.py`.
- [x] `W12.P26.S196` - Close `AFR-094` for `src/aeat/application/auth/_apoderado.py` with signals `secure-object, secure-bound, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/auth/_apoderado.py`.
- [x] `W12.P26.S197` - Close `AFR-095` for `src/aeat/application/auth/_diagnostics.py` with signals `secure-object, active-profile`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/auth/_diagnostics.py`.
- [x] `W12.P26.S198` - Close `AFR-096` for `src/aeat/application/auth/_operator.py` with signals `secure-object, active-profile, manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/auth/_operator.py`.
- [x] `W12.P26.S199` - Close `AFR-097` for `src/aeat/application/auth/_sessions.py` with signals `active-profile, manifest-bucket, master-key, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/auth/_sessions.py`.
- [x] `W12.P26.S200` - Close `AFR-098` for `src/aeat/application/calculations/_iva_compensation_history.py` with signals `secure-bound`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `W12.P26.S201` - Close `AFR-099` for `src/aeat/application/calculations/_observations_repository.py` with signals `secure-object, secure-bound`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W12.P26.S202` - Close `AFR-100` for `src/aeat/application/config_reset.py` with signals `secure-object, manifest-bucket, sql-route`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/config_reset.py`.
- [x] `W12.P26.S203` - Close `AFR-101` for `src/aeat/application/diagnostics.py` with signals `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/diagnostics.py`.
- [x] `W12.P26.S204` - Close `AFR-102` for `src/aeat/application/evidence/_models.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/evidence/_models.py`.
- [x] `W12.P26.S205` - Close `AFR-103` for `src/aeat/application/evidence/_service.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/evidence/_service.py`.
- [x] `W12.P26.S206` - Close `AFR-104` for `src/aeat/application/export/_tabular.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/export/_tabular.py`.
- [x] `W12.P26.S207` - Close `AFR-105` for `src/aeat/application/filing/__init__.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/filing/__init__.py`.
- [x] `W12.P26.S208` - Close `AFR-106` for `src/aeat/application/filing/_history_repository.py` with signals `secure-object, secure-bound, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/filing/_history_repository.py`.
- [x] `W12.P26.S209` - Close `AFR-107` for `src/aeat/application/filing/_review.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/filing/_review.py`.
- [x] `W12.P26.S210` - Close `AFR-108` for `src/aeat/application/filing/_runtime_repository.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/filing/_runtime_repository.py`.
- [x] `W12.P26.S211` - Close `AFR-109` for `src/aeat/application/filing/_testing_registry.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/filing/_testing_registry.py`.
- [x] `W12.P26.S212` - Close `AFR-110` for `src/aeat/application/filing/runtime.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/filing/runtime.py`.
- [x] `W12.P26.S213` - Close `AFR-111` for `src/aeat/application/inventory/_service.py` with signals `secure-object, secure-bound, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/inventory/_service.py`.
- [x] `W12.P26.S214` - Close `AFR-112` for `src/aeat/application/invoices/_importing.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/invoices/_importing.py`.
- [x] `W12.P26.S215` - Close `AFR-113` for `src/aeat/application/invoices/_linking.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/application/invoices/_linking.py`.
- [x] `W12.P26.S216` - Close `AFR-114` for `src/aeat/application/invoices/_queries.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/application/invoices/_queries.py`.
- [x] `W12.P26.S217` - Close `AFR-115` for `src/aeat/application/invoices/_reconciliation.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/application/invoices/_reconciliation.py`.
- [x] `W12.P26.S218` - Close `AFR-116` for `src/aeat/application/invoices/_source_resolver.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/application/invoices/_source_resolver.py`.
- [x] `W12.P26.S219` - Close `AFR-117` for `src/aeat/application/ledger/_actions.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/ledger/_actions.py`.
- [x] `W12.P26.S220` - Close `AFR-118` for `src/aeat/application/ledger/_business_operation_invoice.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/ledger/_business_operation_invoice.py`.
- [x] `W12.P26.S221` - Close `AFR-119` for `src/aeat/application/ledger/_evidence.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/ledger/_evidence.py`.
- [x] `W12.P26.S222` - Close `AFR-120` for `src/aeat/application/ledger/_models.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/ledger/_models.py`.
- [x] `W12.P26.S223` - Close `AFR-121` for `src/aeat/application/ledger/_preflight.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/ledger/_preflight.py`.
- [x] `W12.P26.S224` - Close `AFR-122` for `src/aeat/application/ledger/_ratios.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/ledger/_ratios.py`.
- [x] `W12.P26.S225` - Close `AFR-123` for `src/aeat/application/live/__init__.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/live/__init__.py`.
- [x] `W12.P26.S226` - Close `AFR-124` for `src/aeat/application/live/_borrador_100.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/live/_borrador_100.py`.
- [x] `W12.P26.S227` - Close `AFR-125` for `src/aeat/application/live/_censo.py` with signals `secure-object, manifest-bucket, sql-route, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/live/_censo.py`.
- [x] `W12.P26.S228` - Close `AFR-126` for `src/aeat/application/live/_expedientes.py` with signals `secure-object, manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/live/_expedientes.py`.
- [x] `W12.P26.S229` - Close `AFR-127` for `src/aeat/application/live/_notifications.py` with signals `secure-object, manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/live/_notifications.py`.
- [x] `W12.P26.S230` - Close `AFR-128` for `src/aeat/application/live/_snapshot_base.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/live/_snapshot_base.py`.
- [x] `W12.P26.S231` - Close `AFR-129` for `src/aeat/application/live/_verify.py` with signals `secure-object, manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/live/_verify.py`.
- [x] `W12.P26.S232` - Close `AFR-130` for `src/aeat/application/modelo/__init__.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/modelo/__init__.py`.
- [x] `W12.P26.S233` - Close `AFR-131` for `src/aeat/application/modelo/_actions.py` with signals `secure-object, manifest-bucket, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/modelo/_actions.py`.
- [x] `W12.P26.S234` - Close `AFR-132` for `src/aeat/application/modelo/_binding_readiness.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/modelo/_binding_readiness.py`.
- [x] `W12.P26.S235` - Close `AFR-133` for `src/aeat/application/modelo/_borrador_binding.py` with signals `secure-object, manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `W12.P26.S236` - Close `AFR-134` for `src/aeat/application/modelo/_export.py` with signals `active-profile, manifest-bucket, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/modelo/_export.py`.
- [x] `W12.P26.S237` - Close `AFR-135` for `src/aeat/application/modelo/_history.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/modelo/_history.py`.
- [x] `W12.P26.S238` - Close `AFR-136` for `src/aeat/application/modelo/_profile_binding.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W12.P26.S239` - Close `AFR-137` for `src/aeat/application/modelo/_reconcile.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/modelo/_reconcile.py`.
- [x] `W12.P26.S240` - Close `AFR-138` for `src/aeat/application/operator_surface/_contract.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/operator_surface/_contract.py`.
- [x] `W12.P26.S241` - Close `AFR-139` for `src/aeat/application/operator_surface/_crud_contract.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/operator_surface/_crud_contract.py`.
- [x] `W12.P26.S242` - Close `AFR-140` for `src/aeat/application/operator_surface/_help.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/operator_surface/_help.py`.
- [x] `W12.P26.S243` - Close `AFR-141` for `src/aeat/application/operator_surface/_models.py` with signals `active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/operator_surface/_models.py`.
- [x] `W12.P26.S244` - Close `AFR-142` for `src/aeat/application/overview/__init__.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/overview/__init__.py`.
- [x] `W12.P26.S245` - Close `AFR-143` for `src/aeat/application/registry/__init__.py` with signals `secure-object, plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/registry/__init__.py`.
- [x] `W12.P26.S246` - Close `AFR-144` for `src/aeat/application/registry/_corpus.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/registry/_corpus.py`.
- [x] `W12.P26.S247` - Close `AFR-145` for `src/aeat/application/repair_integrity.py` with signals `secure-object, secure-bound, active-profile, manifest-bucket, master-key`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/repair_integrity.py`.
- [x] `W12.P26.S248` - Close `AFR-146` for `src/aeat/application/review/_adapters.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/review/_adapters.py`.
- [x] `W12.P26.S249` - Close `AFR-147` for `src/aeat/application/review/_aggregator.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/review/_aggregator.py`.
- [x] `W12.P26.S250` - Close `AFR-148` for `src/aeat/application/review/_edit.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/review/_edit.py`.
- [x] `W12.P26.S251` - Close `AFR-149` for `src/aeat/application/review/_filter.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/review/_filter.py`.
- [x] `W12.P26.S252` - Close `AFR-150` for `src/aeat/application/review/_operator.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/review/_operator.py`.
- [x] `W12.P26.S253` - Close `AFR-151` for `src/aeat/application/setup/_contracts.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/setup/_contracts.py`.
- [x] `W12.P26.S254` - Close `AFR-152` for `src/aeat/application/setup/_service.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/setup/_service.py`.
- [x] `W12.P26.S255` - Close `AFR-153` for `src/aeat/application/state_projection.py` with signals `runtime, active-profile, manifest-bucket, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/state_projection.py`.
- [x] `W12.P26.S256` - Close `AFR-154` for `src/aeat/application/storage/calc_sheets/_engine.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/storage/calc_sheets/_engine.py`.
- [x] `W12.P26.S257` - Close `AFR-155` for `src/aeat/application/storage/calc_sheets/_layout.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/storage/calc_sheets/_layout.py`.
- [x] `W12.P26.S258` - Close `AFR-156` for `src/aeat/application/storage/calc_sheets/_parity_harness.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/storage/calc_sheets/_parity_harness.py`.
- [x] `W12.P26.S259` - Close `AFR-157` for `src/aeat/application/storage/calc_sheets/_records.py` with signals `secure-object, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/storage/calc_sheets/_records.py`.
- [x] `W12.P26.S260` - Close `AFR-158` for `src/aeat/application/storage/calc_sheets/_translator.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/storage/calc_sheets/_translator.py`.
- [x] `W12.P26.S261` - Close stale `AFR-159` for absent `src/aeat/application/topics/__init__.py` with signals `plain-file`, target `retired`, and owner `W12.P24.S96`; `src/aeat/application/topics/__init__.py`.
- [x] `W12.P26.S262` - Close `AFR-160` for `src/aeat/application/user_profile/__init__.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/user_profile/__init__.py`.
- [x] `W12.P26.S263` - Close `AFR-161` for `src/aeat/application/user_profile/_aggregate.py` with signals `active-profile, manifest-bucket, sql-route, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/user_profile/_aggregate.py`.
- [x] `W12.P26.S264` - Close `AFR-162` for `src/aeat/application/user_profile/_censo_sync.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W12.P26.S265` - Close `AFR-163` for `src/aeat/application/user_profile/_integrity.py` with signals `manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/user_profile/_integrity.py`.
- [x] `W12.P26.S266` - Close `AFR-164` for `src/aeat/application/user_profile/_language_resolver.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/user_profile/_language_resolver.py`.
- [x] `W12.P26.S267` - Close `AFR-165` for `src/aeat/application/user_profile/_lifecycle.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `W12.P26.S268` - Close `AFR-166` for `src/aeat/application/user_profile/_orchestration.py` with signals `secure-object, active-profile, manifest-bucket, sql-route, plain-file`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `W12.P26.S269` - Close `AFR-167` for `src/aeat/application/user_profile/_profile_repository.py` with signals `secure-object, active-profile, manifest-bucket, master-key, sql-route, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/user_profile/_profile_repository.py`.
- [x] `W12.P26.S270` - Close `AFR-168` for `src/aeat/application/user_profile/_repository.py` with signals `secure-object, runtime, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/user_profile/_repository.py`.
- [x] `W12.P26.S271` - Close `AFR-169` for `src/aeat/application/user_profile/_testing.py` with signals `secure-object, active-profile`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/user_profile/_testing.py`.
- [x] `W12.P26.S272` - Close `AFR-170` for `src/aeat/application/verification/_verify.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/verification/_verify.py`.
- [x] `W12.P26.S273` - Close `AFR-171` for `src/aeat/application/wizard/_commands.py` with signals `active-profile, manifest-bucket, master-key`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/wizard/_commands.py`.
- [x] `W12.P26.S274` - Close `AFR-172` for `src/aeat/application/wizard/_persistence.py` with signals `active-profile, manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/wizard/_persistence.py`.
- [x] `W12.P26.S275` - Close `AFR-173` for `src/aeat/application/wizard/_prompter.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/wizard/_prompter.py`.
- [x] `W12.P26.S276` - Close `AFR-174` for `src/aeat/application/wizard/_status.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/wizard/_status.py`.
- [x] `W12.P26.S277` - Close `AFR-175` for `src/aeat/application/wizard/_translations.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/wizard/_translations.py`.
- [x] `W12.P26.S278` - Close `AFR-176` for `src/aeat/application/wizard/_widgets.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/application/wizard/_widgets.py`.
- [x] `W12.P26.S279` - Close `AFR-177` for `src/aeat/application/workflow/__init__.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/workflow/__init__.py`.
- [x] `W12.P26.S280` - Close `AFR-178` for `src/aeat/application/workflow/_errors.py` with signals `active-profile, manifest-bucket, master-key`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/workflow/_errors.py`.
- [x] `W12.P26.S281` - Close `AFR-179` for `src/aeat/application/workflow/_events.py` with signals `manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/application/workflow/_events.py`.
- [x] `W12.P26.S282` - Close `AFR-180` for `src/aeat/application/workflow/_models.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/workflow/_models.py`.
- [x] `W12.P26.S283` - Close `AFR-181` for `src/aeat/application/workflow/_persistence.py` with signals `secure-object, runtime, active-profile, manifest-bucket, master-key, sql-route`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/application/workflow/_persistence.py`.
- [x] `W12.P26.S284` - Close `AFR-182` for `src/aeat/application/workflow/_profile_bucket_scan.py` with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/workflow/_profile_bucket_scan.py`.
- [x] `W12.P26.S285` - Close `AFR-183` for `src/aeat/application/workflow/_profile_health.py` with signals `active-profile, manifest-bucket, master-key, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/application/workflow/_profile_health.py`.
- [x] `W12.P26.S286` - Close `AFR-184` for `src/aeat/core/_bucket_pointer.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/core/_bucket_pointer.py`.
- [x] `W12.P26.S287` - Close `AFR-185` for `src/aeat/core/_bucket_pointer_io.py` with signals `active-profile, manifest-bucket, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/core/_bucket_pointer_io.py`.
- [x] `W12.P26.S288` - Close `AFR-186` for `src/aeat/core/_toml.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/_toml.py`.
- [x] `W12.P26.S289` - Close `AFR-187` for `src/aeat/core/access_gate/__init__.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/access_gate/__init__.py`.
- [x] `W12.P26.S290` - Close `AFR-188` for `src/aeat/core/config.py` with signals `active-profile, manifest-bucket, master-key, sql-route, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/core/config.py`.
- [x] `W12.P26.S291` - Close `AFR-189` for `src/aeat/core/corpus_manifest/__init__.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/corpus_manifest/__init__.py`.
- [x] `W12.P26.S292` - Close `AFR-190` for `src/aeat/core/env_io.py` with signals `master-key, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/core/env_io.py`.
- [x] `W12.P26.S293` - Close `AFR-191` for `src/aeat/core/errors/registry/_adapters.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/core/errors/registry/_adapters.py`.
- [x] `W12.P26.S294` - Close `AFR-192` for `src/aeat/core/errors/registry/_application.py` with signals `active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/core/errors/registry/_application.py`.
- [x] `W12.P26.S295` - Close `AFR-193` for `src/aeat/core/errors/registry/_core.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/errors/registry/_core.py`.
- [x] `W12.P26.S296` - Close `AFR-194` for `src/aeat/core/external_constants.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/core/external_constants.py`.
- [x] `W12.P26.S297` - Close `AFR-195` for `src/aeat/core/file_permissions.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/file_permissions.py`.
- [x] `W12.P26.S298` - Close `AFR-196` for `src/aeat/core/i18n/_render.py` with signals `active-profile, manifest-bucket, sql-route, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/core/i18n/_render.py`.
- [x] `W12.P26.S299` - Close `AFR-197` for `src/aeat/core/locks.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/locks.py`.
- [x] `W12.P26.S300` - Close `AFR-198` for `src/aeat/core/logging.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/logging.py`.
- [x] `W12.P26.S301` - Close `AFR-199` for `src/aeat/core/observability/__init__.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/__init__.py`.
- [x] `W12.P26.S302` - Close `AFR-200` for `src/aeat/core/observability/_context.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/core/observability/_context.py`.
- [x] `W12.P26.S303` - Close `AFR-201` for `src/aeat/core/observability/_errors.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/_errors.py`.
- [x] `W12.P26.S304` - Close `AFR-202` for `src/aeat/core/observability/_fingerprint.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/_fingerprint.py`.
- [x] `W12.P26.S305` - Close `AFR-203` for `src/aeat/core/observability/_models.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/_models.py`.
- [x] `W12.P26.S306` - Close `AFR-204` for `src/aeat/core/observability/_recorder.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/_recorder.py`.
- [x] `W12.P26.S307` - Close `AFR-205` for `src/aeat/core/observability/_sink.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/observability/_sink.py`.
- [x] `W12.P26.S308` - Close `AFR-206` for `src/aeat/core/observability/_store.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/core/observability/_store.py`.
- [x] `W12.P26.S309` - Close `AFR-207` for `src/aeat/core/output_rendering.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/output_rendering.py`.
- [x] `W12.P26.S310` - Close `AFR-208` for `src/aeat/core/paths.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/paths.py`.
- [x] `W12.P26.S311` - Close `AFR-209` for `src/aeat/core/resources/_boundary.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/resources/_boundary.py`.
- [x] `W12.P26.S312` - Close `AFR-210` for `src/aeat/core/resources/_repos/legal_parameters.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/resources/_repos/legal_parameters.py`.
- [x] `W12.P26.S313` - Close `AFR-211` for `src/aeat/core/resources/_repos/modelos.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/core/resources/_repos/modelos.py`.
- [x] `W12.P26.S314` - Close `AFR-212` for `src/aeat/diagnostics/__main__.py` with signals `secure-object`, target `runtime-default`, and owner `W12.P21.S83`; `src/aeat/diagnostics/__main__.py`.
- [x] `W12.P26.S315` - Close `AFR-213` for `src/aeat/diagnostics/profile.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/diagnostics/profile.py`.
- [x] `W12.P26.S316` - Close `AFR-214` for `src/aeat/domain/_secure_storage_runtime.py` with signals `secure-object, runtime, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/_secure_storage_runtime.py`.
- [x] `W12.P26.S317` - Close `AFR-215` for `src/aeat/domain/attachments/_models.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/attachments/_models.py`.
- [x] `W12.P26.S318` - Close `AFR-216` for `src/aeat/domain/auth/apoderamientos/_catalogue.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/auth/apoderamientos/_catalogue.py`.
- [x] `W12.P26.S319` - Close `AFR-217` for `src/aeat/domain/buckets/__init__.py` with signals `secure-object`, target `runtime-default`, and owner `W12.P21.S83`; `src/aeat/domain/buckets/__init__.py`.
- [x] `W12.P26.S320` - Close `AFR-218` for `src/aeat/domain/buckets/_event.py` with signals `manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/buckets/_event.py`.
- [x] `W12.P26.S321` - Close `AFR-219` for `src/aeat/domain/buckets/_event_repository.py` with signals `secure-object, runtime, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S83`; `src/aeat/domain/buckets/_event_repository.py`.
- [x] `W12.P26.S322` - Close `AFR-220` for `src/aeat/domain/calculations/registry/_bindings.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W12.P26.S323` - Close `AFR-221` for `src/aeat/domain/calculations/registry/_export_parse.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_export_parse.py`.
- [x] `W12.P26.S324` - Close `AFR-222` for `src/aeat/domain/calculations/registry/_formula_runtime.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W12.P26.S325` - Close `AFR-223` for `src/aeat/domain/calculations/registry/_legal.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_legal.py`.
- [x] `W12.P26.S326` - Close `AFR-224` for `src/aeat/domain/calculations/registry/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W12.P26.S327` - Close `AFR-225` for `src/aeat/domain/calculations/registry/_parity_tapes.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_parity_tapes.py`.
- [x] `W12.P26.S328` - Close `AFR-226` for `src/aeat/domain/calculations/registry/_record_design.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `W12.P26.S329` - Close `AFR-227` for `src/aeat/domain/calculations/registry/_schema.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W12.P26.S330` - Close `AFR-228` for `src/aeat/domain/calculations/registry/_snapshot.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_snapshot.py`.
- [x] `W12.P26.S331` - Close `AFR-229` for `src/aeat/domain/calculations/registry/_sources.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_sources.py`.
- [x] `W12.P26.S332` - Close `AFR-230` for `src/aeat/domain/calculations/registry/_validate_evidence.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_validate_evidence.py`.
- [x] `W12.P26.S333` - Close `AFR-231` for `src/aeat/domain/calculations/registry/_workbook_parity.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/calculations/registry/_workbook_parity.py`.
- [x] `W12.P26.S334` - Close `AFR-232` for `src/aeat/domain/categories/_registry.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/categories/_registry.py`.
- [x] `W12.P26.S335` - Close `AFR-233` for `src/aeat/domain/deadlines/_engine.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/deadlines/_engine.py`.
- [x] `W12.P26.S336` - Close `AFR-234` for `src/aeat/domain/deadlines/_festivos.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/deadlines/_festivos.py`.
- [x] `W12.P26.S337` - Close `AFR-235` for `src/aeat/domain/deadlines/_recargo.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/deadlines/_recargo.py`.
- [x] `W12.P26.S338` - Close `AFR-236` for `src/aeat/domain/filing/_complementaria_repository.py` with signals `secure-object, manifest-bucket, plain-file`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/filing/_complementaria_repository.py`.
- [x] `W12.P26.S339` - Close `AFR-237` for `src/aeat/domain/filing/_repository.py` with signals `secure-object, secure-bound, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/filing/_repository.py`.
- [x] `W12.P26.S340` - Close `AFR-238` for `src/aeat/domain/filing/_runtime_repository.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/filing/_runtime_repository.py`.
- [x] `W12.P26.S341` - Close `AFR-239` for `src/aeat/domain/fincas/_imputacion_parameters.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/fincas/_imputacion_parameters.py`.
- [x] `W12.P26.S342` - Close `AFR-240` for `src/aeat/domain/invoices/_models.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/invoices/_models.py`.
- [x] `W12.P26.S343` - Close `AFR-241` for `src/aeat/domain/invoices/_repository.py` with signals `secure-object, runtime, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/invoices/_repository.py`.
- [x] `W12.P26.S344` - Close `AFR-242` for `src/aeat/domain/iva/_catalogue.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/iva/_catalogue.py`.
- [x] `W12.P26.S345` - Close `AFR-243` for `src/aeat/domain/iva/_rates.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/iva/_rates.py`.
- [x] `W12.P26.S346` - Close `AFR-244` for `src/aeat/domain/iva/_recargo_equivalencia.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/iva/_recargo_equivalencia.py`.
- [x] `W12.P26.S347` - Close `AFR-245` for `src/aeat/domain/iva/_schema.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/iva/_schema.py`.
- [x] `W12.P26.S348` - Close `AFR-246` for `src/aeat/domain/justificante/_repository.py` with signals `secure-bound`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/justificante/_repository.py`.
- [x] `W12.P26.S349` - Close `AFR-247` for `src/aeat/domain/manuals/_fetch.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/manuals/_fetch.py`.
- [x] `W12.P26.S350` - Close `AFR-248` for `src/aeat/domain/manuals/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/manuals/_loader.py`.
- [x] `W12.P26.S351` - Close `AFR-249` for `src/aeat/domain/manuals/_verify.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/manuals/_verify.py`.
- [x] `W12.P26.S352` - Close `AFR-250` for `src/aeat/domain/manuals/errors.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/manuals/errors.py`.
- [x] `W12.P26.S353` - Close `AFR-251` for `src/aeat/domain/modelos/_calculation_repository.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/modelos/_calculation_repository.py`.
- [x] `W12.P26.S354` - Close `AFR-252` for `src/aeat/domain/modelos/_filing_record.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W12.P26.S355` - Close `AFR-253` for `src/aeat/domain/modelos/_filing_repository.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/modelos/_filing_repository.py`.
- [x] `W12.P26.S356` - Close `AFR-254` for `src/aeat/domain/modelos/_repository.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/modelos/_repository.py`.
- [x] `W12.P26.S357` - Close `AFR-255` for `src/aeat/domain/modelos/_runtime_repository.py` with signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/modelos/_runtime_repository.py`.
- [x] `W12.P26.S358` - Close `AFR-256` for `src/aeat/domain/modelos/_verification_repository.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/modelos/_verification_repository.py`.
- [x] `W12.P26.S359` - Close `AFR-257` for `src/aeat/domain/modelos/_work_unit.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/modelos/_work_unit.py`.
- [x] `W12.P26.S360` - Close `AFR-258` for `src/aeat/domain/normatives/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/normatives/_loader.py`.
- [x] `W12.P26.S361` - Close `AFR-259` for `src/aeat/domain/renta/_substrate.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/renta/_substrate.py`.
- [x] `W12.P26.S362` - Close `AFR-260` for `src/aeat/domain/submission/_models.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/submission/_models.py`.
- [x] `W12.P26.S363` - Close `AFR-261` for `src/aeat/domain/submission/_preflight.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/submission/_preflight.py`.
- [x] `W12.P26.S364` - Close `AFR-262` for `src/aeat/domain/submission/_protocols.py` with signals `plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/domain/submission/_protocols.py`.
- [x] `W12.P26.S365` - Close `AFR-263` for `src/aeat/domain/submission/_repository.py` with signals `secure-bound`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/submission/_repository.py`.
- [x] `W12.P26.S366` - Close `AFR-264` for `src/aeat/domain/transactions/_errors.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/transactions/_errors.py`.
- [x] `W12.P26.S367` - Close `AFR-265` for `src/aeat/domain/transactions/_models.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/transactions/_models.py`.
- [x] `W12.P26.S368` - Close `AFR-266` for `src/aeat/domain/transactions/_raw_transaction.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `W12.P26.S369` - Close `AFR-267` for `src/aeat/domain/transactions/_repository.py` with signals `secure-object, runtime, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/transactions/_repository.py`.
- [x] `W12.P26.S370` - Close `AFR-268` for `src/aeat/domain/usage_ratios/_model.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/usage_ratios/_model.py`.
- [x] `W12.P26.S371` - Close `AFR-269` for `src/aeat/domain/usage_ratios/_service.py` with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`; `src/aeat/domain/usage_ratios/_service.py`.
- [x] `W12.P26.S372` - Close `AFR-270` for `src/aeat/domain/user_profile/_loader.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/domain/user_profile/_loader.py`.
- [x] `W12.P26.S373` - Close `AFR-271` for `src/aeat/domain/user_profile/_values.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/domain/user_profile/_values.py`.
- [x] `W12.P26.S374` - Close `AFR-272` for `src/aeat/entrypoints/cli/__init__.py` with signals `active-profile, manifest-bucket, master-key, sql-route, plain-file`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W12.P26.S375` - Close `AFR-273` for `src/aeat/entrypoints/cli/_app_live.py` with signals `secure-object, active-profile, manifest-bucket, plain-file`, target `runtime-default`, and owner `W12.P21.S83`; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W12.P26.S376` - Close `AFR-274` for `src/aeat/entrypoints/cli/_bootstrap_exempt.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/entrypoints/cli/_bootstrap_exempt.py`.
- [x] `W12.P26.S377` - Close `AFR-275` for `src/aeat/entrypoints/cli/_common.py` with signals `active-profile, manifest-bucket, sql-route`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W12.P26.S378` - Close `AFR-276` for `src/aeat/entrypoints/cli/_config/__init__.py` with signals `secure-object, active-profile, manifest-bucket, master-key, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W12.P26.S379` - Close `AFR-277` for `src/aeat/entrypoints/cli/_config/_google.py` with signals `secure-object, active-profile, plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W12.P26.S380` - Close `AFR-278` for `src/aeat/entrypoints/cli/_config/_profile_censo.py` with signals `active-profile, manifest-bucket`, target `bootstrap-custody`, and owner `W12.P22.S89`; `src/aeat/entrypoints/cli/_config/_profile_censo.py`.
- [x] `W12.P26.S381` - Close `AFR-279` for `src/aeat/entrypoints/cli/_errors.py` with signals `master-key`, target `runtime-default`, and owner `W12.P20.S78`; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W12.P26.S382` - Close `AFR-280` for `src/aeat/entrypoints/cli/_ledger.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W12.P26.S383` - Close `AFR-281` for `src/aeat/entrypoints/cli/_modelo.py` with signals `active-profile, manifest-bucket, sql-route, plain-file`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W12.P26.S384` - Close `AFR-282` for `src/aeat/entrypoints/cli/_modelo_payloads.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W12.P26.S385` - Close `AFR-283` for `src/aeat/entrypoints/cli/_overview.py` with signals `active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W12.P26.S386` - Close `AFR-284` for `src/aeat/entrypoints/cli/_overview_rendering.py` with signals `active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_overview_rendering.py`.
- [x] `W12.P26.S387` - Close `AFR-285` for `src/aeat/entrypoints/cli/_review.py` with signals `manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_review.py`.
- [x] `W12.P26.S388` - Close `AFR-286` for `src/aeat/entrypoints/cli/_review_payloads.py` with signals `manifest-bucket, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/entrypoints/cli/_review_payloads.py`.
- [x] `W12.P26.S389` - Close `AFR-287` for `src/aeat/entrypoints/cli/_root_landing.py` with signals `active-profile`, target `manifest-discovery`, and owner `W12.P22.S90`; `src/aeat/entrypoints/cli/_root_landing.py`.
- [x] `W12.P26.S390` - Close `AFR-288` for `src/aeat/entrypoints/cli/_schemas.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/entrypoints/cli/_schemas.py`.
- [x] `W12.P26.S391` - Close `AFR-289` for `src/aeat/entrypoints/cli/_tty.py` with signals `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`; `src/aeat/entrypoints/cli/_tty.py`.
- [x] `W12.P26.S392` - Close `AFR-290` for `src/aeat/entrypoints/cli/registry.py` with signals `plain-file, secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S85`; `src/aeat/entrypoints/cli/registry.py`.
- [x] `W12.P26.S393` - Close `AFR-291` for `src/aeat/locales/_ast_scanner.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/locales/_ast_scanner.py`.
- [x] `W12.P26.S394` - Close `AFR-292` for `src/aeat/locales/cli.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/locales/cli.py`.
- [x] `W12.P26.S395` - Close `AFR-293` for `src/aeat/locales/manager.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`; `src/aeat/locales/manager.py`.

## Wave `W13` - fresh CLI persona findings adoption

This Wave adopts testimonial-driven CLI findings that affect storage readiness, repair guidance, and operator confidence. Findings must be reconciled against existing persona audits and capability research before any repair is assigned to this plan.

### Phase `W13.P27` - testimonial disposition reconciliation

Reconcile fresh persona testimony with current secure-storage, readiness, repair, and CLI workflow plans so each finding has exactly one owning plan row or an explicit deferred disposition.

- [x] `W13.P27.S396` - Reconcile fresh persona audits and repair plans with secure-storage readiness ownership; `.vault/audit`.
- [x] `W13.P27.S397` - Record research requirements for persona findings that lack enough architectural backing; `.vault/research`.
- [x] `W13.P27.S398` - Classify unresolved persona findings as secure-storage, CLI workflow, capability, or separate-plan work; `.vault/plan`.

#### S398 classification register

S398 classifies the unresolved testimonial findings after S396 reconciliation and S397 research. This register is binding for W13.P28 sequencing: only secure-storage-owned rows proceed to S399 retest and S400 repair adoption inside this plan.

| Finding | Classification | Secure-storage disposition | Next owner |
|---|---|---|---|
| FRESH-004 manual route discoverability | CLI workflow / capability discovery | Not secure-storage-owned on current evidence. Registry manual/source authority and formula reference output are the relevant surfaces; no storage readiness, custody, repair, or profile-bound evidence failure is shown. | External CLI/capability plan if an alias, help bridge, or richer formula hint is desired. |
| FRESH-007 profile-filtered obligation explanation | CLI workflow / capability discovery | Not secure-storage-owned on current evidence. `overview explain` and calendar own applicability reasoning; the remaining issue is post-profile guidance/discovery unless a future retest proves the overview surface cannot read the stored profile through runtime. | External CLI/capability plan for next-action guidance; reopen here only if runtime-backed profile reads fail. |
| FRESH-011 undecryptable stored draft readiness blocker | Secure-storage readiness / repair integrity | Secure-storage-owned. Existing architecture already requires degraded storage readiness and fail-closed filing-grade behavior; W15 repair privacy/integrity rows provide the current diagnostic and redaction baseline. | S399 retest, then S400 only if retest finds a secure-storage repair gap. |
| REPAIR-PROFILE-PRIVACY-001 repair-profile identifier leakage | Secure-storage repair privacy | Secure-storage-owned but already remediated. This wave treats it as a regression-check input, not a new repair row. | S399/S401 synthesis only unless retest leaks raw identifiers. |

### Phase `W13.P28` - testimonial retest and repair adoption

Run fresh persona retests only after ownership is explicit, then add or execute secure-storage-owned repair rows with isolated scratch roots and CLI-only operator paths.

- [x] `W13.P28.S399` - Dispatch fresh persona retests for secure-storage-owned workflows with isolated scratch roots; `.vault/exec`.
- [x] `W13.P28.S400` - Adopt secure-storage-owned testimonial repairs into plan rows before implementation; `.vault/plan`.
- [x] `W13.P28.S401` - Persist testimonial retest synthesis and final finding dispositions; `.vault/audit`.

#### S400 repair-adoption register

S400 adopts no new secure-storage repair rows from the S399 retest pass. The focused secure-storage-owned findings remain covered by existing implementation and regression gates:

| Finding | S399 evidence | S400 decision |
|---|---|---|
| FRESH-011 undecryptable stored draft readiness blocker | Clean Modelo 111 readiness passes with explicit preflight scope; unreadable secure-object rows surface through metadata-only repair integrity diagnostics; backend unreadable-row grouping/listing tests pass. | No new repair row. Keep S401 synthesis as final disposition and reopen only if a future retest shows readiness consumes degraded storage silently or repair diagnostics leak private data. |
| REPAIR-PROFILE-PRIVACY-001 repair-profile identifier leakage | Repair profile, integrity objects, quarantine dry-run, and fresh-root repair bootstrap gates pass with real isolated fixtures. | No new repair row. Treat as remediated regression coverage in S401. |

## Wave `W14` - ModeloDraft roundtrip fixture hardening

This Wave records late roundtrip-fixture hardening work that was originally grafted into W07 with a high step number. It now sits after the W12 inventory so canonical step identifiers remain unique and monotonic.

### Phase `W14.P29` - ModeloDraft roundtrip fixture hardening

Populate all optional ModeloDraft fields with non-default values in roundtrip fixtures so a save-drops-field / load-re-defaults-field regression cannot pass vacuously. Extend the anti-tautology companion with parametrized field-drop proofs for each previously-defaulted optional field.

- [x] `W14.P29.S402` - Populate 6 optional ModeloDraft fields (casilla_provenance, notes, approved_at, approved_by, review_checksum, approval_basis) with non-default values in both roundtrip fixtures; `extend anti-tautology suite with 6 parametrized field-drop cases; all 9 tests pass, ruff clean; `src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py`.

## Wave `W15` - post-migration stabilization and guard closeout

This Wave converts the post-migration findings into executable work before more broad storage refactoring proceeds. It stabilizes the current Modelo validation boundary, reconciles repair privacy contracts, turns residual string scans into enforceable guards, inventories storage hierarchy constants and namespace ownership, and closes vaultspec traceability for the pushed migration waves.

### Phase `W15.P30` - Modelo validation boundary stabilization

Restore the current shared HEAD to a trustworthy baseline before further secure-storage work by isolating and repairing the Modelo work-create validation refusal that blocks focused CLI verification.

- [x] `W15.P30.S403` - Reproduce the current Modelo work-create validation refusal and isolate the rejecting boundary; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W15.P30.S404` - Repair the Modelo validation boundary so valid work-create inputs are not masked by generic CLI validation refusal; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W15.P30.S405` - Run the affected Modelo CLI suites through the centralized runtime helper and record any non-storage registry blockers; `src/aeat/entrypoints/cli`.

### Phase `W15.P31` - repair privacy contract reconciliation

Reconcile the repair CLI command surface with the privacy contract so diagnostics remain useful while row context, logs, and operator output do not leak active profile identifiers or secure-storage internals.

- [x] `W15.P31.S406` - Reconcile current repair CLI verbs with the privacy-contract tests and remove obsolete command assumptions; `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`.
- [x] `W15.P31.S407` - Harden repair diagnostics so row context and diagnostic logs redact profile identifiers and object-key hints; `src/aeat/application/repair_integrity.py`.
- [x] `W15.P31.S408` - Add real-custody CLI privacy roundtrips for repair list, quarantine, bootstrap, and log surfaces; `src/aeat/entrypoints/cli`.

### Phase `W15.P32` - residual storage-surface guard hardening

Turn the residual deprecated-token scan into durable guard coverage so intentional explicit-route tests remain allowed while new low-level env, passphrase, or repository shortcuts are rejected.

- [x] `W15.P32.S409` - Add guard coverage against direct passphrase-env imports and unapproved explicit database-url test setup; `src/aeat/adapters/persistence/storage`.
- [x] `W15.P32.S410` - Require CLI storage tests to use centralized Settings or secure-sql runtime helpers instead of naked AEAT env wrangling; `src/aeat/tests`.
- [x] `W15.P32.S411` - Persist an approved residual-hit inventory for cold-start leak guards and explicit-route refusal tests; `.vault/audit`.

### Phase `W15.P33` - storage hierarchy constants and namespace inventory

Make storage hierarchy and namespace shape auditable before deeper refactors by inventorying constants, object-key grammar, manifest versions, repair classifications, and duplicated local values.

- [x] `W15.P33.S412` - Inventory bucket paths, object-key grammar, namespace strings, manifest schema versions, and repair classifications; `.vault/audit`.
- [x] `W15.P33.S413` - Promote storage hierarchy constants and namespace identities into typed registry models; `src/aeat/adapters/persistence/storage`.
- [x] `W15.P33.S414` - Replace duplicated local storage namespace and key constants with the typed registry entries; `src/aeat/application`.

### Phase `W15.P34` - vaultspec traceability closeout

Close the process gap left by fast shared-worktree execution by recording the pushed storage-migration commits, validation caveats, residual blockers, and review requirements in durable vault artifacts.

- [x] `W15.P34.S415` - Persist step records for the pushed storage test-enrollment commits and their validation results; `.vault/exec`.
- [x] `W15.P34.S416` - Persist closeout audit for residual storage blockers, intentional guard hits, and required code-review follow-up; `.vault/audit`.

## Wave `W16` - audit observation pool reconciliation

Ensure every secure-storage audit observation is inventoried, mapped to an owning plan row or disposition, and guarded for future execution waves.

### Phase `W16.P35` - observation inventory and ownership map

Extract all open audit observations and assign each to an existing step, a new step, or an explicit disposition.

- [x] `W16.P35.S417` - Inventory secure-storage audit artifacts and extract each open observation, blocker, residual risk, review follow-up, and approved exception into a single observation pool; `.vault/audit`.
- [x] `W16.P35.S418` - Map every observation-pool item to an existing Step id, newly required Step id, or explicit out-of-scope disposition; `.vault/plan`.

### Phase `W16.P36` - observation adoption and closeout

Persist remaining owners, add missing executable rows, and enforce review-time owner linkage for future secure-storage findings.

- [x] `W16.P36.S419` - Persist observation-pool closeout with remaining owners, deferrals, and review signoff; `.vault/audit`.
- [x] `W16.P36.S420` - Add missing plan rows or wave assignments for secure-storage observations that lack an existing executable owner; `.vault/plan`.
- [x] `W16.P36.S421` - Add a recurring guard that future secure-storage audit findings cite an owning plan row before execution continues; `.vault/audit`.

## Wave `W17` - ledger side-store migration follow-up

This Wave adopts the ledger JSONL side stores discovered during W05.P09.S36 without disrupting canonical plan ordering. It requires the purchase-invoice evidence and business-operation invoice stores to migrate behind runtime-created secure-object repositories, or to receive explicit exception ADR coverage if migration is rejected after implementation research.

### Phase `W17.P37` - ledger JSONL secure-object migration

Close the two W05.P09.S36 ledger side-store findings with runtime-created secure-object repositories or an explicit ADR-backed exception before the side-store hardening campaign is treated as complete. Both rows are identified-not-started slices until their repositories or exception ADRs land.

- [x] `W17.P37.S424` - identified-not-started: migrate purchase invoice evidence JSONL persistence behind runtime-created secure-object repositories; `src/aeat/application/ledger/_evidence.py`.
- [x] `W17.P37.S425` - identified-not-started: migrate payable and collectible business-operation invoice JSONL persistence behind runtime-created secure-object repositories; `src/aeat/application/ledger/_business_operation_invoice.py`.

## Wave `W18` - split-module affected-file closeout

Close pending affected-file rows introduced by modelo split-module work so the runtime rollout review has a complete register.

### Phase `W18.P38` - modelo split-module register closure

Assign one executable closeout row to each pending modelo projection, selector, work-addressing, work-policy, plazo, IVA wallet, and CLI split module.

- [x] `W18.P38.S442` - Close AFR-294 for src/aeat/application/modelo/_projection.py with signals active-profile, manifest-bucket, plain-file, target manifest-discovery, and owner W18.P38.S442; `src/aeat/application/modelo/_projection.py`.
- [x] `W18.P38.S443` - Close AFR-295 for src/aeat/application/modelo/_selectors.py with signals active-profile, manifest-bucket, target manifest-discovery, and owner W18.P38.S443; `src/aeat/application/modelo/_selectors.py`.
- [x] `W18.P38.S444` - Close AFR-296 for src/aeat/application/modelo/_work_addressing.py with signals active-profile, manifest-bucket, target manifest-discovery, and owner W18.P38.S444; `src/aeat/application/modelo/_work_addressing.py`.
- [x] `W18.P38.S445` - Close AFR-297 for src/aeat/application/modelo/_work_create_policy.py with signals active-profile, plain-file, target manifest-discovery, and owner W18.P38.S445; `src/aeat/application/modelo/_work_create_policy.py`.
- [x] `W18.P38.S446` - Close AFR-298 for src/aeat/application/modelo/_work_plazo.py with signals active-profile, manifest-bucket, plain-file, target manifest-discovery, and owner W18.P38.S446; `src/aeat/application/modelo/_work_plazo.py`.
- [x] `W18.P38.S447` - Close AFR-299 for src/aeat/application/modelo/_iva_wallet_seed.py with signals active-profile, manifest-bucket, plain-file, target manifest-discovery, and owner W18.P38.S447; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [x] `W18.P38.S448` - Close AFR-300 for src/aeat/entrypoints/cli/_modelo_projection_cli.py with signals active-profile, plain-file, target manifest-discovery, and owner W18.P38.S448; `src/aeat/entrypoints/cli/_modelo_projection_cli.py`.
- [x] `W18.P38.S449` - Close AFR-301 for src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py with signals active-profile, manifest-bucket, plain-file, target manifest-discovery, and owner W18.P38.S449; `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`.

## Wave `W19` - secure-storage guard verification repair

Keep the secure-storage guard tests aligned with current split-module paths so runtime rollout verification remains executable after concurrent refactors.

### Phase `W19.P39` - guard inventory path alignment

Refresh secure-storage guard approvals and production-write inventory paths after test and application split-module moves, without weakening the guard assertions.

- [x] `W19.P39.S450` - Refresh secure-storage guard approval paths and production-write inventory after split-module moves; `src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py; src/aeat/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`.

## Wave `W20` - observation-pool adopted follow-ups

Adopt the remaining W16 observation-pool work that is still real after the broad runtime rollout: recovery API exposure, passphrase and redaction handling, residual environment/test exceptions, filing localization, provenance path privacy, and central CLI redaction enrollment. These rows are follow-up work, not W16 blockers, because W16's job is to make every observation owned.

### Phase `W20.P40` - custody API and secret redaction follow-up

Close the oldest custody and passphrase observations with current command-surface evidence and centralized redaction behavior.

- [x] `W20.P40.S451` - Verify recovery lock unlock rekey recover show-recovery and verify-recovery command/API exposure against the accepted custody architecture and add missing owner rows for absent accepted operations; `src/aeat/entrypoints/cli/_config; src/aeat/adapters/persistence/storage/master_key`.
- [x] `W20.P40.S452` - Harden passphrase environment bootstrap and central redaction handling so passphrase material is one-shot where feasible, logs/prints stay centrally redacted, and remaining env-based custody tests have explicit Settings-backed justification; `src/aeat/core; src/aeat/adapters/persistence/storage/master_key; src/aeat/entrypoints/cli`.
- [x] `W20.P40.S457` - Implement first-class config custody verbs for lock unlock rekey recover show-recovery and verify-recovery using the accepted recovery facade and bucket session lifecycle; `src/aeat/entrypoints/cli/_config; src/aeat/adapters/persistence/storage/master_key; src/aeat/locales`.
- [x] `W20.P40.S458` - Replace stale custody and recovery guidance with canonical config custody verbs and locale-backed recovery copy; `src/aeat/adapters/persistence/storage/master_key; src/aeat/adapters/persistence/storage/runtime.py; src/aeat/core/errors/registry; src/aeat/locales`.
- [x] `W20.P40.S459` - Implement and localize the first-class `config lock` and `config unlock` custody aliases through the existing profile lifecycle session path, with real CLI coverage; `src/aeat/entrypoints/cli/_config; src/aeat/entrypoints/cli/tests; src/aeat/locales`.
- [x] `W20.P40.S460` - Close post-S458 stale guidance drift by routing runtime, diagnostics, operator help, repair next actions, registry suggestions, and locale recovery copy to canonical `config unlock` and `config recover` verbs; `src/aeat/adapters/persistence/storage; src/aeat/application; src/aeat/entrypoints/cli; src/aeat/core/errors/registry; src/aeat/locales`.
- [x] `W20.P40.S461` - Decide and implement the `config profile switch` compatibility contract after `config unlock` adoption: either retire the command surface with migration coverage or keep it as an explicit compatibility alias hidden from recovery guidance; `src/aeat/entrypoints/cli/_config; src/aeat/entrypoints/cli/tests; src/aeat/locales; .vault/adr`.

### Phase `W20.P41` - convention and provenance privacy follow-up

Retire residual convention exceptions or make them explicit, localized, and privacy-safe.

- [x] `W20.P41.S453` - Retire or narrow residual direct environment, monkeypatch, explicit-route, and literal filesystem-layout allowances from the secure-storage guard inventories, preserving only tests whose direct subject is the centralized Settings or low-level SQL contract; `src/aeat/tests; src/aeat/adapters/persistence/storage/tests; .vault/audit`.
- [x] `W20.P41.S454` - Localize remaining filing/modelo builder and calculation error messages through `tr()` and `python -m aeat.locales`, preserving AEAT core exception hierarchy and registry-backed error codes; `src/aeat/application/filing; src/aeat/application/modelo; src/aeat/locales`.
- [x] `W20.P41.S455` - Review inbound parser and provenance path handling for raw PDF paths, byte-stream source labels, `source_pdf_path`, financial provenance, justificante provenance, PDF dispatch cache keys, and sanitizer hash disclosure; `redact or normalize path-bearing data where it can reach persisted state, logs, or user-facing errors; `src/aeat/adapters/inbound; src/aeat/application`.

### Phase `W20.P42` - central redaction enrollment proof

Prove CLI and application output flows use the centralized redaction boundary rather than ad hoc logging or print behavior.

- [x] `W20.P42.S456` - Audit and harden centralized log/print/output redaction enrollment across CLI, diagnostics, repair, live, profile, and remote-mirror surfaces, adding guard coverage for any bypass found; `src/aeat/core; src/aeat/entrypoints/cli; src/aeat/application`.

## Wave `W21` - CLI verification follow-up

Track current-tree CLI startup blockers discovered while exhausting secure-storage verification so backend rollout can be declared against a working command surface.

### Phase `W21.P43` - CLI startup registration repair

Resolve command startup registration failures that prevent real CLI verification from reaching modelo and secure-storage paths.

- [x] `W21.P43.S462` - Root-cause and repair wizard catalogue registration during CLI startup so real modelo command verification reaches application paths instead of failing with INTERNAL startup errors; `src/aeat/entrypoints/cli; src/aeat/application/wizard; src/aeat/core/wizard_catalogue; src/aeat/entrypoints/cli/tests`.
