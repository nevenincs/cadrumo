---
tags:
  - '#plan'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-23'
body_hash: 'sha256:cc0e295ed48ed877a7d0992447d780e120eee1b3d6708bb927b5569aa3cb07f3'
tier: L3
related:
  - '[[2026-08-22-secure-storage-performance-hardening-adr]]'
  - '[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]'
  - '[[2026-08-23-cli-runtime-resource-architecture-convergence-research]]'
  - '[[2026-08-22-secure-storage-performance-hardening-research]]'
  - '[[2026-08-22-secure-storage-performance-hardening-reference]]'
---

# `secure-storage-performance-hardening` plan

## Steps

## Wave `W01` - Measure and classify the complete surface

Establish a reproducible, non-frozen census and attribution baseline for every CLI node before changing loading or storage behavior.

### Phase `W01.P01` - Live command census and capability contract

Make the real installed command tree authoritative for universal enrollment.

- [x] `W01.P01.S01` - Extend the live command walker to emit stable command paths, node kind, loader owner, and handler owner for every reachable node; `src/cadrumo/entrypoints/cli/_command_suggestions.py`.
- [x] `W01.P01.S02` - Define command capability classes covering registry, profile custody, encrypted facts, network, browser, Google, calculation, filing, and state-free behavior; `src/cadrumo/entrypoints/cli/_command_schema.py`.
- [x] `W01.P01.S03` - Introduce lightweight node-attached command execution policy and expose it through the live command census; `src/cadrumo/entrypoints/cli/_command_policy.py and _command_suggestions.py`.
- [x] `W01.P01.S48` - Attach execution policy to every config subtree callback and group; `src/cadrumo/entrypoints/cli/_config/`.
- [x] `W01.P01.S49` - Attach execution policy to every ledger subtree callback and group while retaining legacy risk rows until mandatory S52 consumer migration and deletion; `src/cadrumo/entrypoints/cli/ ledger modules`.
- [x] `W01.P01.S50` - Attach execution policy to every modelo subtree callback and group while retaining legacy risk rows until mandatory S52 consumer migration and complete deletion; `src/cadrumo/entrypoints/cli/ modelo modules`.
- [x] `W01.P01.S51` - Attach execution policy to live, diagnostics, maintenance, review, overview, registry, and quickfile callbacks; `src/cadrumo/entrypoints/cli/ remaining app modules`.
- [x] `W01.P01.S52` - Migrate operator-surface and MCP HITL consumers to live-node execution policy, remove all legacy risk rows, and delete the keyed risk table; `src/cadrumo/application/operator_surface and src/cadrumo/adapters/inbound/mcp`.
- [x] `W01.P01.S53` - Migrate profile-bound write routing to execution-policy scope and delete the verb-path catalogue; `src/cadrumo/application/storage_write_policy.py and src/cadrumo/entrypoints/cli/_common.py`.
- [x] `W01.P01.S04` - Add a universal census gate that fails for every unclassified node and prove the detector against an externally injected node; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.

### Phase `W01.P02` - Reproducible startup and resolution profiler

Attribute cost per live CLI path using real subprocesses.

- [x] `W01.P02.S05` - Add a reusable fresh-process profiler for resolution, invocation, imports, Pydantic construction, filesystem changes, and storage operations; `src/cadrumo/tests/cli_performance.py`.
- [x] `W01.P02.S06` - Add quiet-runner calibration and median and ratio budget support without single-sample pass conditions; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.
- [x] `W01.P02.S07` - Capture baseline distributions and ranked outliers for every enrolled node as execution evidence; `dev/benchmarks/cli/`.
- [x] `W01.P02.S08` - Prove profiler and census gates bite on injected registry loading, filesystem materialization, and unclassified nodes; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.

## Wave `W02` - Make command loading proportional to the selected path

Ensure resolution of any CLI path loads only lightweight metadata plus the capabilities that path declares.

### Phase `W02.P03` - Bootstrap and lazy registration kernel

Generalize lazy loading to nested groups and leaves.

- [x] `W02.P03.S09` - Refactor lazy registration into a reusable node loader with explicit targets and fail-loud dependency classification; `src/cadrumo/entrypoints/cli/_command_suggestions.py`.
- [x] `W02.P03.S10` - Preserve root help, completion, version, error-envelope, and suggestion contracts through metadata-only traversal; `src/cadrumo/entrypoints/cli/_common.py`.
- [x] `W02.P03.S12` - Extend lazy import failure coverage across nested groups and leaves for required and optional dependencies; `src/cadrumo/entrypoints/cli/tests/`.

### Phase `W02.P03a` - Urgent command-authority correction

Correct the nonconforming generated-resource design before any further command-loading or performance work, then make one atomic hard cut to production-authored CommandSpec authority and prove every source, build, shipping, and installed-runtime lane.

- [ ] `W02.P03a.S54` - Atomically hard-cut the complete root, group, and leaf surface to distributed production-authored CommandSpec as sole structural authority, project runtime assembly, help, completion, census, schema, operator, MCP/HITL, execution policy, and write routing from specs, make handlers behavior-only, and delete callback/decorator authority, lazy and path mirrors, both runtime JSON readers, both development generators, ignore entries, cache-parity tests, and stale prose with no fallback, shim, or partial coexistence; `repository CLI command-authority surface`.
- [ ] `W02.P03a.S11` - Correct the reopened S11 execution and review evidence, preserving its latency observations while re-proving schema and operator-help discovery exclusively from production CommandSpec after the atomic cutover; `.vault/exec/2026-08-22-secure-storage-performance-hardening/ and .vault/audit/`.
- [ ] `W02.P03a.S14` - Correct the open S14 evidence by rejecting the app-manifest reader and generator as nonconforming, then re-prove demand-loaded modelo, registry, ledger, live, maintenance, overview, review, diagnostics, and quickfile descendants exclusively from production CommandSpec after the atomic cutover; `.vault/exec/2026-08-22-secure-storage-performance-hardening/ and .vault/audit/`.
- [ ] `W02.P03a.S55` - Add dynamic CommandSpec exact-set, uniqueness, parent-edge, target, locale-key, schema, policy, side-effect, performance-class, and write-route gates for every current and future root, group, and leaf, forbid every former structural authority and runtime artifact edge, and prove each detector with independently constructed missing, duplicate, orphan, malformed, forbidden-import, and undeclared-node negatives; `src/cadrumo/entrypoints/cli/tests/ and dev/ci/tests/`.
- [ ] `W02.P03a.S56` - Prove clean-checkout direct-source and editable-install CLI assembly, help, completion, census, schema, operator, MCP/HITL, and write-routing behavior from tracked CommandSpec modules without generation or development imports, including explicit absence of both command JSON names and generator paths; `src/cadrumo/entrypoints/cli/tests/ and dev/packaging/`.
- [ ] `W02.P03a.S57` - Prove direct-wheel, direct-sdist, and sdist-to-wheel contents and installed behavior include every production CommandSpec module, exclude both command JSON names and development generators, and materialize the complete localized root, group, and leaf surface with resolvable public handler and schema targets; `src/cadrumo/tests/test_wheel_content_boundary.py and dev/packaging/`.
- [ ] `W02.P03a.S58` - Bind one immutable Git-archive Python cohort to exhaustive installed-runtime CommandSpec identities, locale metadata, policy, schema, selected-path import budgets, and artifact absence, then require downstream smoke, Scoop, Homebrew, MCPB, marketplace, and publish lanes to consume that sealed cohort without rebuilding or regenerating command authority; `dev/packaging/ and dev/release/`.
- [ ] `W02.P03a.S59` - Run two independent post-cutover architecture reviews and reconcile all command-authority, production-development boundary, build-lane, shipping-lane, and installed-runtime findings before resuming the remaining performance campaign; `.vault/audit/`.

### Phase `W02.P04` - Enroll every command subtree

Convert the complete CLI to the shared demand-loaded registration shape.

- [x] `W02.P04.S13` - Convert the complete config subtree from eager registrar imports to nested loader references; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W02.P04.S15` - Keep distributed CommandSpec modules import-light by splitting heavyweight handler payload and schema implementations behind owned lazy public targets while retaining all structural declarations in production specs; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P04.S16` - Replace hidden first-party function-local coupling with owned lazy public handler and schema boundaries referenced only by CommandSpec targets; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P04.S17` - Require every current and future CLI root, group, and leaf to be declared exactly once through CommandSpec with no decorator, registrar, callback-metadata, generated-resource, or path-catalogue escape hatch; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.

### Phase `W02.P05` - Lazy public application and configuration boundaries

Stop lightweight handlers paying for broad application and materialization graphs.

- [ ] `W02.P05.S18` - Replace the eager workflow facade with an explicit PEP 562 lazy export map preserving public symbols and direction; `src/cadrumo/application/workflow/__init__.py`.
- [ ] `W02.P05.S19` - Move heavy workflow contracts into cohesive sibling modules loaded only by owning commands; `src/cadrumo/application/workflow/`.
- [ ] `W02.P05.S20` - Separate read-only settings and path calculation from directory, permission, logging, journal, and topology materialization; `src/cadrumo/core/config.py`.
- [ ] `W02.P05.S21` - Add facade parity, cycle, forbidden-import, and read-only-materialization gates; `src/cadrumo/tests/`.

## Wave `W03` - Build the pure secure-storage summary path

Make profile discovery a coherent, authoritative, non-mutating read that never enters cryptographic custody or repair.

### Phase `W03.P06` - Single-observation persistence witness

Recognize commit identity and label provenance once per capsule.

- [ ] `W03.P06.S22` - Add an immutable capsule-summary witness carrying validated commit observation and UUID-bound label provenance; `src/cadrumo/adapters/persistence/storage/custody/_capsule.py`.
- [ ] `W03.P06.S23` - Split pure label-head verification from publication, recovery, and repair; `src/cadrumo/adapters/persistence/storage/custody/_label_head_repository.py`.
- [ ] `W03.P06.S24` - Reuse the anchored discovery observation instead of reopening and revalidating commit members; `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`.
- [ ] `W03.P06.S25` - Add real-filesystem adversarial coverage for link, record, retired-layout, concurrency, denial, and interruption cases; `src/cadrumo/adapters/persistence/storage/custody/tests/`.

### Phase `W03.P07` - Public summary inventory

Expose the minimum authenticated discovery projection.

- [ ] `W03.P07.S26` - Define immutable ProfileSummary and typed degraded and concurrent outcomes at the owning boundary; `src/cadrumo/application/user_profile/_profile_repository.py`.
- [ ] `W03.P07.S27` - Implement summary inventory from recognized witnesses without constructing custody aggregates; `src/cadrumo/application/user_profile/_profile_repository.py`.
- [ ] `W03.P07.S28` - Export summary inventory through the lazy public facade and prove public-name parity; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `W03.P07.S29` - Add real-store empty, populated, malformed, and concurrent inventory tests with deterministic ordering and linear reads; `src/cadrumo/application/user_profile/tests/`.

### Phase `W03.P08` - Single-pass CLI consumption

Join active state once and render without re-entering persistence.

- [ ] `W03.P08.S30` - Route config profile list through public summary inventory and one active-pointer observation; `src/cadrumo/entrypoints/cli/_config/__init__.py`.
- [ ] `W03.P08.S31` - Make profile rendering consume the joined summary without resolving storage again; `src/cadrumo/entrypoints/cli/_common.py`.
- [ ] `W03.P08.S32` - Prove empty and populated listing creates no state and reaches no custody, crypto, session, or repair capability; `src/cadrumo/entrypoints/cli/_config/tests/test_profile_list_performance_contract.py`.

## Wave `W04` - Enforce universal responsiveness and robustness

Turn the architectural properties into permanent gates over every CLI node and ratchet all observed outliers.

### Phase `W04.P09` - Whole-tree import and capability gates

Prove each live node resolution graph is a subset of its declared capabilities.

- [ ] `W04.P09.S33` - Parameterize fresh-process resolution over the dynamic CommandSpec graph and reject undeclared module families for every projected live node; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.
- [ ] `W04.P09.S34` - Keep state-free nodes free of registry, calculation, filing, network, browser, Google, crypto, keyring, and storage materialization; `src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`.
- [ ] `W04.P09.S35` - Defer expensive capability families until the owning leaf executes rather than ancestor or sibling resolution; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.
- [ ] `W04.P09.S36` - Add static and executed import-graph checks for eager cross-layer edges, cycles, and private shortcuts; `src/cadrumo/tests/test_deferred_cross_layer_imports.py`.

### Phase `W04.P10` - Whole-tree latency, scaling, and side-effect gates

Hold every enrolled node to calibrated class budgets.

- [ ] `W04.P10.S37` - Run calibrated resolution and invocation budgets over the exact dynamic CommandSpec graph with class-relative per-path failures and exact parity to projected live nodes; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.
- [ ] `W04.P10.S38` - Add empty, one-profile, and multi-profile scaling lanes using real subprocesses and persisted capsules; `src/cadrumo/entrypoints/cli/tests/test_cli_storage_scaling.py`.
- [ ] `W04.P10.S39` - Assert filesystem equality for read-only nodes and declared write roots for mutating nodes; `src/cadrumo/entrypoints/cli/tests/test_cli_side_effect_contract.py`.
- [ ] `W04.P10.S40` - Action generated outliers until no enrolled path exceeds budget or imports undeclared capabilities; `src/cadrumo/entrypoints/cli/`.

## Wave `W05` - Integrate, audit, and close

Validate the refactor against all behavior, security, architecture, and campaign-level completion criteria.

### Phase `W05.P11` - Regression and security convergence

Preserve CLI schemas, refusal semantics, custody guarantees, and storage roundtrips.

- [ ] `W05.P11.S41` - Run CommandSpec authority, CLI contract, documented-command, help, completion, envelope, localization, profile lifecycle, clean-source, and installed-artifact suites; `src/cadrumo/entrypoints/cli/tests/ and dev/packaging/`.
- [ ] `W05.P11.S42` - Run custody, secure-storage, recovery, unlock, persistence-roundtrip, and adversarial filesystem suites; `src/cadrumo/adapters/persistence/storage/`.
- [ ] `W05.P11.S43` - Run lint, architecture gates, full pytest, and Vaultspec checks and action every in-scope regression; `repository-wide quality gates`.

### Phase `W05.P12` - Independent closure

Prove the entire live CLI and secure-storage goal is satisfied.

- [ ] `W05.P12.S44` - Run the mandated eight-axis structural audit and action every confirmed finding; `.vault/audit/`.
- [ ] `W05.P12.S45` - Perform a fresh-context honesty review and open Steps for every remaining gap; `.vault/audit/`.
- [ ] `W05.P12.S46` - Publish final distributions, import reductions, filesystem effects, populated scaling, and census coverage; `.vault/reference/`.
- [ ] `W05.P12.S47` - Close only when every CommandSpec and projected live node is exactly classified and gated, both forbidden JSON names and development generators are absent from tracked and shipped runtime surfaces, every build and shipping lane is proven, and no review item remains unactioned; `.vault/exec/2026-08-22-secure-storage-performance-hardening/`.
