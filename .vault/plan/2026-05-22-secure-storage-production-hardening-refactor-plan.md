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
  - '[[2026-05-22-secure-object-backlog-drain-r3-P03-summary]]'
  - '[[2026-05-21-fresh-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory]]'
  - '[[2026-05-21-fresh-cli-persona-capability-gap-design]]'
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

- [ ] `W02.P04.S15` - enroll ledger and invoice repositories in runtime-created secure storage; `src/aeat/application/ledger`.
- [ ] `W02.P04.S16` - enroll filing and modelo work-unit repositories in runtime-created secure storage; `src/aeat/application/modelo`.
- [ ] `W02.P04.S17` - enroll AEAT pull, wallet, and live snapshot repositories in runtime-created secure storage; `src/aeat/application/live`.
- [ ] `W02.P04.S18` - enroll auth session and remote provider repositories in runtime-created secure storage; `src/aeat/adapters`.
- [ ] `W02.P04.S19` - add a policy guard against direct production SecureObjectRepository construction; `src/aeat/adapters/persistence/storage`.

## Wave `W03` - namespace registry and schema policy

This Wave makes namespace constants auditable architecture values. It defines ownership, sensitivity, schema, retention, key grammar, partial-read policy, and migration policy for every secure-object namespace.

### Phase `W03.P05` - central namespace registry

Create the typed registry and migrate constants to it without changing encrypted payload semantics.

- [ ] `W03.P05.S20` - define secure-object namespace registry models; `src/aeat/adapters/persistence/storage`.
- [ ] `W03.P05.S21` - register profile, ledger, invoice, filing, wallet, and calculation namespaces; `src/aeat/adapters/persistence/storage`.
- [ ] `W03.P05.S22` - register auth, session, cache, evidence, inventory, and remote-sync namespaces; `src/aeat/adapters/persistence/storage`.
- [ ] `W03.P05.S23` - replace local namespace string constants in application repositories with registry entries; `src/aeat/application`.

### Phase `W03.P06` - namespace policy enforcement

Apply registered namespace policy to repository creation, reads, writes, repair diagnostics, and source resolver degradation.

- [ ] `W03.P06.S24` - require namespace registry entries when constructing runtime repositories; `src/aeat/adapters/persistence/storage`.
- [ ] `W03.P06.S25` - enforce registered sensitivity and schema policy on secure-object reads and writes; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W03.P06.S26` - replace repair namespace marker heuristics with registry ownership metadata; `src/aeat/application/repair_integrity.py`.
- [ ] `W03.P06.S27` - add registry completeness tests for every discovered secure-object namespace; `src/aeat/adapters/persistence/storage`.

## Wave `W04` - revision lineage and fail-closed integrity

This Wave adds storage-level mutation history and makes incomplete sensitive reads explicit. It depends on the runtime and namespace registry because lineage and read policy are namespace-scoped contracts.

### Phase `W04.P07` - secure-object revision metadata

Add lineage fields and write contracts so overwrites become traceable revisions or explicit conflicts.

- [ ] `W04.P07.S28` - extend the secure-object ORM with revision and integrity metadata fields; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [ ] `W04.P07.S29` - write revision ids, previous revision references, hashes, timestamps, and provenance on secure-object saves; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W04.P07.S30` - add compare-and-swap conflict handling for revision-aware writes; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W04.P07.S31` - add migration or bootstrap handling for existing rows without revision metadata; `src/aeat/adapters/persistence/storage/sql`.

### Phase `W04.P08` - fail-closed listing and source degradation

Make partial reads opt-in and propagate unreadable-row diagnostics into calculation readiness.

- [ ] `W04.P08.S32` - make default sensitive namespace listing fail closed on unreadable rows; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W04.P08.S33` - stream iter_records_with_failures in bounded batches; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W04.P08.S34` - propagate storage degradation diagnostics from source resolvers to the calculation mesh; `src/aeat/application`.
- [ ] `W04.P08.S35` - add real-behavior tests for unreadable-row fail-closed and explicit partial reads; `src/aeat/adapters/persistence/storage`.

## Wave `W05` - side-store and remote mirror hardening

This Wave removes or records remaining alternate persistence classes after the core runtime, namespace, and revision contracts exist. It also constrains remote storage to encrypted mirror semantics.

### Phase `W05.P09` - bucket-local side-store resolution

Migrate sensitive JSON and JSONL stores to secure objects or persist accepted exception ADRs before further expansion.

- [ ] `W05.P09.S36` - inventory evidence, ledger, inventory, live, and snapshot bucket-local JSON stores; `src/aeat/application`.
- [ ] `W05.P09.S37` - migrate evidence bundle persistence behind runtime-created secure-object repositories; `src/aeat/application/evidence`.
- [ ] `W05.P09.S38` - migrate inventory persistence behind runtime-created secure-object repositories; `src/aeat/application/inventory`.
- [ ] `W05.P09.S39` - migrate live snapshot persistence behind runtime-created secure-object repositories; `src/aeat/application/live`.
- [ ] `W05.P09.S40` - persist exception ADRs for any retained explicit export or operational side store; `.vault/adr`.

### Phase `W05.P10` - remote ciphertext mirror contract

Constrain remote providers to encrypted object mirroring with revision and integrity metadata, never plaintext application state.

- [ ] `W05.P10.S41` - add remote mirror policy fields to namespace registry entries; `src/aeat/adapters/persistence/storage`.
- [ ] `W05.P10.S42` - store remote mirror manifests with ciphertext hashes and revision watermarks; `src/aeat/adapters`.
- [ ] `W05.P10.S43` - detect partial upload, partial download, stale mirror, and revision conflicts; `src/aeat/adapters`.
- [ ] `W05.P10.S44` - add real-behavior remote mirror tests using opaque encrypted payloads; `src/aeat/adapters`.

## Wave `W06` - adverse-condition gates and closeout

This final Wave proves the refactor works under adverse production conditions and persists the review trail before the SecureStorage API is treated as hardened.

### Phase `W06.P11` - production adverse-condition verification

Exercise the final storage architecture with real code paths, real encrypted stores, and explicit failure assertions.

- [ ] `W06.P11.S45` - add adverse-condition tests for locked, expired, wrong-passphrase, and torn-manifest sessions; `src/aeat/adapters/persistence/storage`.
- [ ] `W06.P11.S46` - add adverse-condition tests for route mismatch, unregistered namespace, and unsecured backend refusal; `src/aeat/adapters/persistence/storage`.
- [ ] `W06.P11.S47` - add adverse-condition tests for revision conflicts and partial remote mirrors; `src/aeat/adapters`.
- [ ] `W06.P11.S48` - run focused storage, config, profile, live, ledger, modelo, and remote provider test gates; `src/aeat`.
- [ ] `W06.P11.S49` - run final SecureStorage code review and persist audit closeout; `.vault/audit`.

## Wave `W07` - classified secure-SQL hygiene backlog adoption

This Wave adopts the remaining classified secure-SQL hygiene backlog into the production hardening plan. It requires inventory and research-backed slice selection before any repair rows are executed, preserving settings-backed isolation and real-behavior test discipline.

### Phase `W07.P12` - classified backlog inventory

Reconcile the remaining classified files with the accepted R1 through R3 repair pattern, identify the next bounded repair slice, and require research or execution notes where repository boundaries are unclear.

- [ ] `W07.P12.S50` - Inventory remaining classified secure-SQL hygiene files and write a research-backed slice map; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [ ] `W07.P12.S51` - Select the next application or CLI hygiene slice after runtime-readiness implications are researched; `src/aeat/application`.
- [ ] `W07.P12.S52` - Validate candidate isolation patterns against settings-backed repository injection before repair; `src/aeat/tests`.
- [ ] `W07.P12.S53` - Select the next domain repository hygiene slice after inventory confirms ownership; `src/aeat/domain`.

### Phase `W07.P13` - classified backlog gates

Close each adopted hygiene slice only after focused tests, the secure-SQL guard, and a review audit prove the slice used real code paths without monkeypatch, fake, stub, or naked environment shortcuts.

- [ ] `W07.P13.S54` - Run the secure-SQL guard and focused repaired-slice tests; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [ ] `W07.P13.S55` - Persist hygiene review and remaining-backlog closeout after each adopted slice; `.vault/audit`.

## Wave `W08` - fresh CLI persona findings adoption

This Wave adopts testimonial-driven CLI findings that affect storage readiness, repair guidance, and operator confidence. Findings must be reconciled against existing persona audits and capability research before any repair is assigned to this plan.

### Phase `W08.P14` - testimonial disposition reconciliation

Reconcile fresh persona testimony with current secure-storage, readiness, repair, and CLI workflow plans so each finding has exactly one owning plan row or an explicit deferred disposition.

- [ ] `W08.P14.S56` - Reconcile fresh persona audits and repair plans with secure-storage readiness ownership; `.vault/audit`.
- [ ] `W08.P14.S57` - Record research requirements for persona findings that lack enough architectural backing; `.vault/research`.
- [ ] `W08.P14.S58` - Classify unresolved persona findings as secure-storage, CLI workflow, capability, or separate-plan work; `.vault/plan`.

### Phase `W08.P15` - testimonial retest and repair adoption

Run fresh persona retests only after ownership is explicit, then add or execute secure-storage-owned repair rows with isolated scratch roots and CLI-only operator paths.

- [ ] `W08.P15.S59` - Dispatch fresh persona retests for secure-storage-owned workflows with isolated scratch roots; `.vault/exec`.
- [ ] `W08.P15.S60` - Adopt secure-storage-owned testimonial repairs into plan rows before implementation; `.vault/plan`.
- [ ] `W08.P15.S61` - Persist testimonial retest synthesis and final finding dispositions; `.vault/audit`.

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
- [ ] `W10.P17.S67` - Audit exception swallowing and require at-least-debug logging or explicit typed degradation records; `src/aeat`.
- [ ] `W10.P17.S68` - Audit secure-storage tests for tautological assertions, fake helpers, stubs, patches, skips, xfails, and mirrored business logic; `src/aeat`.
- [ ] `W10.P17.S69` - Audit environment and storage-route handling for centralized Settings usage and naked env access; `src/aeat`.
- [ ] `W10.P17.S70` - Audit secure-storage implementations for duplicated enums, duplicated models, and missed shared pydantic model reuse; `src/aeat`.

## Wave `W11` - convention hardening remediation

Execute only the convention repairs justified by the W10 evidence review, keeping user-facing text localized, errors registry-bound, swallowed failures observable, tests real-behavior, environment handling settings-backed, and shared models authoritative.

### Phase `W11.P18` - localized errors and exception observability

Repair secure-storage user-facing errors and exception handling only after W10 identifies concrete gaps, preserving centralized translation and typed error contracts.

- [ ] `W11.P18.S71` - Repair user-facing secure-storage messages to use tr-backed locale keys and validate with aeat.locales CLI; `src/aeat`.
- [ ] `W11.P18.S72` - Repair secure-storage exception classes to derive from AEAT core bases with registry-backed error codes; `src/aeat/adapters/persistence/storage`.
- [ ] `W11.P18.S73` - Repair swallowed secure-storage exceptions with debug logging or explicit typed degradation surfaces; `src/aeat`.

### Phase `W11.P19` - settings tests and model reuse hardening

Repair implementation and test gaps where W10 finds naked environment access, tautological tests, or duplicated contracts instead of central Settings, shared enums, and shared pydantic models.

- [ ] `W11.P19.S74` - Repair naked environment handling by routing storage and test configuration through centralized Settings helpers; `src/aeat`.
- [ ] `W11.P19.S75` - Repair tautological or shortcut tests with real-behavior coverage that imports production code directly; `src/aeat`.
- [ ] `W11.P19.S76` - Repair duplicated secure-storage enums and models by reusing core enums, shared models, and pydantic contracts; `src/aeat`.
- [ ] `W11.P19.S77` - Add guard checks for settings-backed environment use, translation coverage, error registry binding, and test-hygiene regressions; `src/aeat`.
