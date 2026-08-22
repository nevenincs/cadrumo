---
tags:
  - '#plan'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_hash: 'sha256:0756d3c536acce54376d7797dd353edaeea9a5273d77c0afed8f7f601a65990e'
tier: L3
related:
  - '[[2026-08-22-secure-storage-performance-hardening-adr]]'
  - '[[2026-08-22-secure-storage-performance-hardening-research]]'
  - '[[2026-08-22-secure-storage-performance-hardening-reference]]'
---

# `secure-storage-performance-hardening` plan

## Description

Execute the approved command-scoped loading and pure secure-storage-read
architecture across the complete installed CLI. Every root, group, leaf, and
callback reachable from the real command tree is enrolled. Coverage derives
from the live tree and fails when a new node lacks loader ownership, capability
classification, import boundaries, side-effect policy, or performance class.
The plan uses structural registration, a generated census, and parameterized
real-process gates rather than a frozen verb count; per-path outlier reports
ensure a cluster Step cannot conceal an individual slow or over-capable leaf.
Secure-storage listing is the first end-to-end exemplar, not a scope boundary.

## Steps

The five ordered Waves establish universal measurement, remove eager loading,
build the pure secure-storage read path, enforce whole-tree budgets, and close
only after independent structural and honesty audits.

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
- [ ] `W01.P01.S52` - Migrate operator-surface and MCP HITL consumers to live-node execution policy, remove all legacy risk rows, and delete the keyed risk table; `src/cadrumo/application/operator_surface and src/cadrumo/adapters/inbound/mcp`.
- [ ] `W01.P01.S53` - Migrate profile-bound write routing to execution-policy scope and delete the verb-path catalogue; `src/cadrumo/application/storage_write_policy.py and src/cadrumo/entrypoints/cli/_common.py`.
- [ ] `W01.P01.S04` - Add a universal census gate that fails for every unclassified node and prove the detector against an externally injected node; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.

### Phase `W01.P02` - Reproducible startup and resolution profiler

Attribute cost per live CLI path using real subprocesses.

- [ ] `W01.P02.S05` - Add a reusable fresh-process profiler for resolution, invocation, imports, Pydantic construction, filesystem changes, and storage operations; `src/cadrumo/tests/cli_performance.py`.
- [ ] `W01.P02.S06` - Add quiet-runner calibration and median and ratio budget support without single-sample pass conditions; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.
- [ ] `W01.P02.S07` - Capture baseline distributions and ranked outliers for every enrolled node as execution evidence; `dev/benchmarks/cli/`.
- [ ] `W01.P02.S08` - Prove profiler and census gates bite on injected registry loading, filesystem materialization, and unclassified nodes; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.

## Wave `W02` - Make command loading proportional to the selected path

Ensure resolution of any CLI path loads only lightweight metadata plus the capabilities that path declares.

### Phase `W02.P03` - Bootstrap and lazy registration kernel

Generalize lazy loading to nested groups and leaves.

- [ ] `W02.P03.S09` - Refactor lazy registration into a reusable node loader with explicit targets and fail-loud dependency classification; `src/cadrumo/entrypoints/cli/_command_suggestions.py`.
- [ ] `W02.P03.S10` - Preserve root help, completion, version, error-envelope, and suggestion contracts through metadata-only traversal; `src/cadrumo/entrypoints/cli/_common.py`.
- [ ] `W02.P03.S11` - Make schema and operator-help discovery consume registration metadata without materializing handler subtrees; `src/cadrumo/entrypoints/cli/_command_schema.py`.
- [ ] `W02.P03.S12` - Extend lazy import failure coverage across nested groups and leaves for required and optional dependencies; `src/cadrumo/entrypoints/cli/tests/`.

### Phase `W02.P04` - Enroll every command subtree

Convert the complete CLI to the shared demand-loaded registration shape.

- [ ] `W02.P04.S13` - Convert the complete config subtree from eager registrar imports to nested loader references; `src/cadrumo/entrypoints/cli/_config/`.
- [ ] `W02.P04.S14` - Convert the complete app subtree including modelo, registry, ledger, live, maintenance, overview, review, diagnostics, and quickfile descendants; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P04.S15` - Split import-heavy payload contracts from handlers so registration imports only option and help metadata; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P04.S16` - Replace hidden first-party function-local coupling with owned lazy public boundaries; `src/cadrumo/entrypoints/cli/`.
- [ ] `W02.P04.S17` - Require every current and future CLI node to use the shared loader contract with no eager registrar escape hatch; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.

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

- [ ] `W04.P09.S33` - Parameterize fresh-process resolution over every live node and reject undeclared module families; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.
- [ ] `W04.P09.S34` - Keep state-free nodes free of registry, calculation, filing, network, browser, Google, crypto, keyring, and storage materialization; `src/cadrumo/entrypoints/cli/tests/test_lazy_command_tree.py`.
- [ ] `W04.P09.S35` - Defer expensive capability families until the owning leaf executes rather than ancestor or sibling resolution; `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`.
- [ ] `W04.P09.S36` - Add static and executed import-graph checks for eager cross-layer edges, cycles, and private shortcuts; `src/cadrumo/tests/test_deferred_cross_layer_imports.py`.

### Phase `W04.P10` - Whole-tree latency, scaling, and side-effect gates

Hold every enrolled node to calibrated class budgets.

- [ ] `W04.P10.S37` - Run calibrated resolution and invocation budgets over the live census with class-relative per-path failures; `src/cadrumo/entrypoints/cli/tests/test_cli_performance_budgets.py`.
- [ ] `W04.P10.S38` - Add empty, one-profile, and multi-profile scaling lanes using real subprocesses and persisted capsules; `src/cadrumo/entrypoints/cli/tests/test_cli_storage_scaling.py`.
- [ ] `W04.P10.S39` - Assert filesystem equality for read-only nodes and declared write roots for mutating nodes; `src/cadrumo/entrypoints/cli/tests/test_cli_side_effect_contract.py`.
- [ ] `W04.P10.S40` - Action generated outliers until no enrolled path exceeds budget or imports undeclared capabilities; `src/cadrumo/entrypoints/cli/`.

## Wave `W05` - Integrate, audit, and close

Validate the refactor against all behavior, security, architecture, and campaign-level completion criteria.

### Phase `W05.P11` - Regression and security convergence

Preserve CLI schemas, refusal semantics, custody guarantees, and storage roundtrips.

- [ ] `W05.P11.S41` - Run CLI contract, documented-command, help, completion, envelope, localization, and profile lifecycle suites; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W05.P11.S42` - Run custody, secure-storage, recovery, unlock, persistence-roundtrip, and adversarial filesystem suites; `src/cadrumo/adapters/persistence/storage/`.
- [ ] `W05.P11.S43` - Run lint, architecture gates, full pytest, and Vaultspec checks and action every in-scope regression; `repository-wide quality gates`.

### Phase `W05.P12` - Independent closure

Prove the entire live CLI and secure-storage goal is satisfied.

- [ ] `W05.P12.S44` - Run the mandated eight-axis structural audit and action every confirmed finding; `.vault/audit/`.
- [ ] `W05.P12.S45` - Perform a fresh-context honesty review and open Steps for every remaining gap; `.vault/audit/`.
- [ ] `W05.P12.S46` - Publish final distributions, import reductions, filesystem effects, populated scaling, and census coverage; `.vault/reference/`.
- [ ] `W05.P12.S47` - Close only when every live node is classified and gated and no review item remains unactioned; `.vault/exec/2026-08-22-secure-storage-performance-hardening/`.

## Parallelization

W01 is the hard prerequisite because its live census, capability taxonomy, and
profiler define completion. After P01 and P02 land, P03 and P05 may proceed in
parallel. Within P04, config and app subtree conversion can run concurrently
under disjoint directory ownership; S17 joins them. W03 begins after P05 and
proceeds persistence-first: P06 before P07 before P08. W04 depends on the loader
contract and summary inventory, while P09 and P10 may run in parallel. W05 begins
only after W02 through W04 converge. Every lane consumes the same live census;
no worker may maintain a private verb list.

## Verification

Universal enrollment is proven by materializing the real command tree and
requiring exact-set coverage for every reachable root, group, leaf, and callback.
Each node carries loader ownership, capability classification, side-effect
policy, and a calibrated performance class. Adding a command automatically adds
a required case; an externally injected unclassified node proves the detector
bites without hardcoding the current command count.

Fresh-process probes separate bootstrap, resolution, and handler execution and
report every path. Import-family gates prove ancestor and sibling resolution do
not load registry or other undeclared authorities. Real persisted profile stores
prove empty and populated behavior, bounded linear reads, coherent concurrency
outcomes, zero custody/crypto/repair capability during listing, and zero
read-only filesystem mutation. Full CLI, custody, persistence, architecture,
lint, pytest, and Vaultspec gates must pass before the mandated eight-axis audit
and fresh-context honesty review. The campaign cannot close while any live node
is unenrolled, any class budget fails, or any review finding remains unactioned.
