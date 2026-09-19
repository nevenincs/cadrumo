---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:bd13183b13b15581fc3e2eac6a059ad4ea6c9841ec139f728d95756f0e4d9962'
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

**Resolution re-review (2026-09-14): Resolved.** `CapturedProfileSchema` now carries the resolved path, immutable bytes, and parsed schema through the receipt, compilation cache, structural validation, and publication candidate. The post-validation receipt still re-reads the live path only to refuse mutation; compilation consumes the captured object. The A-to-B-to-A capture regression test passed.

### point-loading-closure | high | A revision request hydrates the whole fact catalogue and duplicates export layouts

`dev/registry/compiler/authority_database.py` assigns every governed-fact query to every modelo revision, followed by its legal/source references. The reviewed generated database contains 158 fact components and 163 to 346 dependencies per revision. The same compiler encodes each complete `ModeloRevision`, including `export_layouts`, and also emits 96 separately addressed export-layout components; filing consumers continue reading layouts from the embedded revision. A point revision or snapshot is therefore not bounded to the selected model's declared dependencies, and layout payloads are duplicated rather than loaded on demand. The prepared acceptance tests assert a lazy profile component but do not instrument all component families or reject this whole-catalogue closure.

**Resolution re-review (2026-09-14): Resolved.** The compiler stores base revisions with `export_layouts=()`, emits layouts only as addressed components, and derives fact dependency edges from strict decode-observed queries rather than attaching the complete catalogue. A pinned snapshot composes layouts from the selected revision and generation. Focused database point-load and generation tests passed.

### usage-ratio-pinned-scope | high | Existing encrypted usage-ratio profiles cannot be decoded by ordinary ledger composition

`src/cadrumo/domain/usage_ratios/model.py` makes membership in `ELIGIBLE_USAGE_RATIO_CATEGORIES` resolve through the current governed-fact `ContextVar`. Any non-empty `UsageRatioProfile` construction or Pydantic decode therefore refuses outside a pinned authority operation. `src/cadrumo/entrypoints/ledger_action_composition.py` calls `load_usage_ratios` while composing ports, before opening such an operation, and the persistence adapter's signature cannot receive one. A real direct construction with one registry-shaped category exited 1 with `eligible_usage_ratio_categories requires an explicit generation-pinned governed-fact scope`. Empty profiles mask the regression because their eligibility loop performs no membership query. This makes previously stored encrypted ratios unreadable on ordinary ledger commands.

**Resolution re-review (2026-09-14): Resolved for valid profiles.** Secure decode now requires an explicit `PinnedAuthorityOperation`; real ledger composition opens that operation and the decoded profile retains only an immutable private eligibility set. `with_ratio` and `without_ratio` preserve that witness through pure copies and perform no later authority read. Taxpayer ratios remain in the encrypted secure-object repository. Invalid-key error rendering has a narrower remaining defect recorded below.

### eager-json-retirement | high | The displaced eager JSON authority remains a production-module API and accepts two v5 payload shapes

`src/cadrumo/domain/calculations/registry/authority.py` still defines `bundled_authority`, `published_authority`, the JSON artifact locator, process cache, and eager `ValidatedRegistryAuthority` runtime surface. `src/cadrumo/domain/calculations/registry/authority_artifact.py` still owns the complete v5 JSON frame reader/writer and explicitly accepts payloads both with and without `profile_schema`. Package exclusions prevent installed fallback, and no production consumer currently calls `bundled_authority`, but documenting these source APIs as development-only does not retire the displaced runtime path. The optional same-version shape is unowned legacy compatibility, contrary to S114, the cutover decision, and the no-legacy rule; development comparison belongs behind a development-only boundary with one captured baseline shape.

**Resolution re-review (2026-09-14): Resolved.** Production bundled/published JSON loaders, locator, and shared eager cache are removed. The remaining complete-frame helpers are private codec primitives consumed by `dev.registry.authority_json`; that development baseline requires exactly the profile-complete v5 payload members. Package-boundary tests explicitly reject `authority.json` from wheel and sdist contents, so no legacy dual shape remains in the installed runtime.

### concurrent-cache-cycle | high | Cross-thread dependency cycles deadlock instead of refusing

`AccountedAuthorityCache` detects recursion only through a thread-local key stack. If one loader owns A and waits for in-flight B while another owns B and waits for in-flight A, both block in `Future.result()` and neither releases its in-flight entry. A focused two-thread probe left both daemon threads alive with `in_flight == 2`. Runtime admission checks foreign keys and counts but does not prove the dependency graph acyclic, so a malformed digest-consistent database can trigger the hang. This violates the explicit prompt cycle/concurrency refusal and turns a typed refusal into an unbounded operation stall.

**Resolution re-review (2026-09-14): Resolved.** The cache maintains owner and waiter edges under one lock and refuses a newly closed cross-thread wait cycle; cleanup releases both in-flight entries. SQLite admission independently validates the full dependency DAG before first use. The two-owner A-to-B/B-to-A bounded-completion test and the admission-cycle test passed.

### publication-ownership | medium | The public validated-database installer does not own the publication lock

`publish_sqlite_authority_candidate` locks the descriptor before calling `install_validated_authority_database`, but the installer is itself public and is called directly by acceptance/promotion preparation. It compiles, exclusively creates a content-addressed file, stages the descriptor, and cleans retired files without acquiring that lock. Concurrent direct installers can race the existence check/create and descriptor replacement; one can fail with an incidental filesystem exception or race a different generation rather than observing the publisher's deterministic single-owner contract.

**Resolution re-review (2026-09-14): Resolved.** The public installer now acquires the descriptor publication lock and delegates to a private lock-owned implementation; the full publisher calls the private form while already holding that same lock. Concurrent different-generation public installation passed and left the descriptor selecting one complete installed database.

### cache-accounting-evidence | medium | Production retention weights and acceptance tests do not prove the 64 MiB decoded-object bound

The database compiler sets each component's `retained_weight` to encoded payload byte length, and the reader charges only that value for the decoded Pydantic object. No estimator relates encoded bytes to retained decoded memory, and production loads never supply shared-weight tokens. The cache tests validate synthetic declared numbers but do not fill real concurrent components, prove production shared references are charged once, or prove caller-held values survive eviction. Telemetry can consequently remain below 64 MiB while retained decoded objects exceed the advertised accounted budget.

**Resolution re-review (2026-09-14): Resolved at the ownership boundary.** On first use the reader charges the greater of the stored payload weight and a cycle-safe decoded immutable-graph estimate; the LRU budget accounts retained values while caller-held and leased values remain explicitly outside cache ownership. Shared-token accounting is retained for graphs that declare shared ownership. Focused decoded-graph, oversize, eviction-survival, concurrent-coalescing, and failure cleanup tests passed.

### lazy-eligibility-error-rendering | medium | Invalid persisted usage-ratio keys are formatted after the pinned scope closes

`load_usage_ratios` correctly validates encrypted payloads inside `validating_governed_facts(operation)`, but its `ValidationError` handler runs after that context manager exits. `_summarise_validation_errors` calls `_unknown_ratio_key_line`, which iterates the lazy `ELIGIBLE_USAGE_RATIO_CATEGORIES` Set and therefore attempts a new authority projection without a pinned scope. A focused synthetic Pydantic enum-error probe exited 1 with `InternalInvariantError: eligible_usage_ratio_categories requires an explicit generation-pinned governed-fact scope`. A malformed or stale encrypted ratio key is fail-closed, but the promised `UsageRatioPersistenceError` and operator-readable eligible-key diagnostic are masked by an internal invariant error.

### canonical-candidate-evidence | medium | The exact final candidate cohort has not completed against stable source inputs

The code-level re-review resolves the original five high and two medium findings, but release acceptance remains unproven while the concurrent canonical registry-authoring lane changes category/source fixtures. The bounded reviewer cohort reported 21 passing tests and 22 failures in stale usage-ratio static category-member fixtures, with three tests deselected by the repository marker policy. Those failures are distinct from the indexed-storage implementation, but checkpoint C, installed/package verification, performance comparison, and exact-byte promotion cannot be accepted or reused until one isolated candidate is compiled and tested after those source inputs stabilize.

## Recommendations

The first seven recommendations below are retained as the historical closure criteria for their corresponding findings; the 2026-09-14 re-review dispositions record that implementation has satisfied them. The remaining release work is:

- Keep invalid-key diagnostics inside the supplied pinned operation, or pass the profile's captured immutable eligibility into the formatter, so malformed encrypted payloads consistently surface UsageRatioPersistenceError without opening another authority operation.
- After the registry-authoring lane stabilizes, compile one isolated candidate, run checkpoint C plus installed/package and quantitative performance checks against that exact descriptor/database pair, and promote only those accepted bytes.

- Resolve `source-capture` before candidate acceptance by making one immutable capture object carry profile bytes and the parsed schema through identity, cache, validation, and database compilation; remove optional ambient compiler entry points or confine bundled default resolution to one development composition boundary. Add a deterministic mid-compile mutation test that proves a typed component cannot differ from its receipt.
- Resolve `point-loading-closure` before performance/cutover acceptance by compiling revision-specific dependency IDs, removing layouts from the base revision payload, and explicitly composing requested layouts only for filing operations. Add the ADR-required all-family hydration trace and assert representative model/fact/profile/evidence requests touch only their declared closures.
- Resolve `usage-ratio-pinned-scope` before release by threading the active `PinnedAuthorityOperation` (or an immutable eligibility value derived from it) through usage-ratio creation and secure decode. Exercise a non-empty encrypted profile through the real ledger composition path; keep the lazy set from opening a hidden authority operation.
- Resolve `eager-json-retirement` before S134 by moving the paired baseline runner/codec to `dev/registry`, deleting the production eager loaders and JSON locator/cache, and requiring one profile-complete baseline payload shape. Update remaining tests and development tooling to import the development definition directly.
- Resolve `concurrent-cache-cycle` before cutover by validating the complete dependency DAG at admission and/or tracking a wait-for graph so cross-thread cycles fail promptly. Add the two-owner A-to-B/B-to-A case with a bounded completion assertion.
- Resolve `publication-ownership` by making the unlocked installer private or making it acquire the descriptor lock itself without double locking; add concurrent different-generation publication evidence through the one public publisher.
- Resolve `cache-accounting-evidence` by defining a conservative decoded retained-weight estimator, using shared tokens where objects are actually shared, and running the quantitative real-component concurrent fill/oversize/eviction/failure cases required by the ADR.
