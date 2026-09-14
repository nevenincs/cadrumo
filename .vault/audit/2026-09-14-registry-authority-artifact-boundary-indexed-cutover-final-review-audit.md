---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:3f59995724887210e35d492bb31d0c2630eeea595771ed94b57bf755bded3c26'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-source-enrollment-reference]]"
---
# `registry-authority-artifact-boundary` audit: `indexed cutover final review`

## Scope

Reviewed the integrated indexed-authority cutover against the accepted storage ADR, source-enrollment reference, execution plan, and always-on repository rules. The review covered the S13 query/generation/profile contexts, source capture and compiler identity, SQLite admission and dependency loading, cache lifetime/accounting, publication and cleanup, profile custody, eager-path retirement, installed archive selection, and the usage-ratio eligibility projection. Concurrent canonical-exception remediation was treated as out of scope except where its live edits intersected these contracts.

The archive policy and installed-oracle code select exactly one descriptor/database pair and exclude authored AEAT data, raw profile TOML, and the JSON artifact. Taxpayer profile values remain behind encrypted secure-object persistence; the public authority stores only the public profile declaration. Those reviewed boundaries produced no separate finding.

## Findings

### source-capture | high | Profile schema compilation re-reads mutable input after deriving its cache identity

`dev/registry/compiler/authority.py` reads and parses the profile path in `compile_validated_authority` to derive `source_receipt`, discards the typed result, and then a cache miss calls `_compile_validated_authority_uncached` / `compile_structural_authority`, which reads and parses the path again. `AuthoritySourceSet` also carries paths rather than an immutable captured payload, while the older optional-path entry points retain an ambient sibling default. A transient A-to-B-to-A edit can therefore build schema B under cache/receipt A and evade the outer before/after receipt equality if the path has returned to A by the final check. This breaks the decision's capture-once identity invariant and can publish a generation whose logical receipt does not describe its typed profile component.

### point-loading-closure | high | A revision request hydrates the whole fact catalogue and duplicates export layouts

`dev/registry/compiler/authority_database.py` assigns every governed-fact query to every modelo revision, followed by its legal/source references. The reviewed generated database contains 158 fact components and 163 to 346 dependencies per revision. The same compiler encodes each complete `ModeloRevision`, including `export_layouts`, and also emits 96 separately addressed export-layout components; filing consumers continue reading layouts from the embedded revision. A point revision or snapshot is therefore not bounded to the selected model's declared dependencies, and layout payloads are duplicated rather than loaded on demand. The prepared acceptance tests assert a lazy profile component but do not instrument all component families or reject this whole-catalogue closure.

### usage-ratio-pinned-scope | high | Existing encrypted usage-ratio profiles cannot be decoded by ordinary ledger composition

`src/cadrumo/domain/usage_ratios/model.py` makes membership in `ELIGIBLE_USAGE_RATIO_CATEGORIES` resolve through the current governed-fact `ContextVar`. Any non-empty `UsageRatioProfile` construction or Pydantic decode therefore refuses outside a pinned authority operation. `src/cadrumo/entrypoints/ledger_action_composition.py` calls `load_usage_ratios` while composing ports, before opening such an operation, and the persistence adapter's signature cannot receive one. A real direct construction with one registry-shaped category exited 1 with `eligible_usage_ratio_categories requires an explicit generation-pinned governed-fact scope`. Empty profiles mask the regression because their eligibility loop performs no membership query. This makes previously stored encrypted ratios unreadable on ordinary ledger commands.

### eager-json-retirement | high | The displaced eager JSON authority remains a production-module API and accepts two v5 payload shapes

`src/cadrumo/domain/calculations/registry/authority.py` still defines `bundled_authority`, `published_authority`, the JSON artifact locator, process cache, and eager `ValidatedRegistryAuthority` runtime surface. `src/cadrumo/domain/calculations/registry/authority_artifact.py` still owns the complete v5 JSON frame reader/writer and explicitly accepts payloads both with and without `profile_schema`. Package exclusions prevent installed fallback, and no production consumer currently calls `bundled_authority`, but documenting these source APIs as development-only does not retire the displaced runtime path. The optional same-version shape is unowned legacy compatibility, contrary to S114, the cutover decision, and the no-legacy rule; development comparison belongs behind a development-only boundary with one captured baseline shape.

### concurrent-cache-cycle | high | Cross-thread dependency cycles deadlock instead of refusing

`AccountedAuthorityCache` detects recursion only through a thread-local key stack. If one loader owns A and waits for in-flight B while another owns B and waits for in-flight A, both block in `Future.result()` and neither releases its in-flight entry. A focused two-thread probe left both daemon threads alive with `in_flight == 2`. Runtime admission checks foreign keys and counts but does not prove the dependency graph acyclic, so a malformed digest-consistent database can trigger the hang. This violates the explicit prompt cycle/concurrency refusal and turns a typed refusal into an unbounded operation stall.

### publication-ownership | medium | The public validated-database installer does not own the publication lock

`publish_sqlite_authority_candidate` locks the descriptor before calling `install_validated_authority_database`, but the installer is itself public and is called directly by acceptance/promotion preparation. It compiles, exclusively creates a content-addressed file, stages the descriptor, and cleans retired files without acquiring that lock. Concurrent direct installers can race the existence check/create and descriptor replacement; one can fail with an incidental filesystem exception or race a different generation rather than observing the publisher's deterministic single-owner contract.

### cache-accounting-evidence | medium | Production retention weights and acceptance tests do not prove the 64 MiB decoded-object bound

The database compiler sets each component's `retained_weight` to encoded payload byte length, and the reader charges only that value for the decoded Pydantic object. No estimator relates encoded bytes to retained decoded memory, and production loads never supply shared-weight tokens. The cache tests validate synthetic declared numbers but do not fill real concurrent components, prove production shared references are charged once, or prove caller-held values survive eviction. Telemetry can consequently remain below 64 MiB while retained decoded objects exceed the advertised accounted budget.

## Recommendations

- Resolve `source-capture` before candidate acceptance by making one immutable capture object carry profile bytes and the parsed schema through identity, cache, validation, and database compilation; remove optional ambient compiler entry points or confine bundled default resolution to one development composition boundary. Add a deterministic mid-compile mutation test that proves a typed component cannot differ from its receipt.
- Resolve `point-loading-closure` before performance/cutover acceptance by compiling revision-specific dependency IDs, removing layouts from the base revision payload, and explicitly composing requested layouts only for filing operations. Add the ADR-required all-family hydration trace and assert representative model/fact/profile/evidence requests touch only their declared closures.
- Resolve `usage-ratio-pinned-scope` before release by threading the active `PinnedAuthorityOperation` (or an immutable eligibility value derived from it) through usage-ratio creation and secure decode. Exercise a non-empty encrypted profile through the real ledger composition path; keep the lazy set from opening a hidden authority operation.
- Resolve `eager-json-retirement` before S134 by moving the paired baseline runner/codec to `dev/registry`, deleting the production eager loaders and JSON locator/cache, and requiring one profile-complete baseline payload shape. Update remaining tests and development tooling to import the development definition directly.
- Resolve `concurrent-cache-cycle` before cutover by validating the complete dependency DAG at admission and/or tracking a wait-for graph so cross-thread cycles fail promptly. Add the two-owner A-to-B/B-to-A case with a bounded completion assertion.
- Resolve `publication-ownership` by making the unlocked installer private or making it acquire the descriptor lock itself without double locking; add concurrent different-generation publication evidence through the one public publisher.
- Resolve `cache-accounting-evidence` by defining a conservative decoded retained-weight estimator, using shared tokens where objects are actually shared, and running the quantitative real-component concurrent fill/oversize/eviction/failure cases required by the ADR.
