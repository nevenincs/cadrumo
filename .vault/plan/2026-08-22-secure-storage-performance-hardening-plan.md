---
tags:
  - '#plan'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
tier: L3
related:
  - '[[2026-08-22-secure-storage-performance-hardening-adr]]'
  - '[[2026-08-22-secure-storage-performance-hardening-research]]'
  - '[[2026-08-22-secure-storage-performance-hardening-reference]]'
modified: '2026-08-22'
body_schema: body-v1
body_hash: 'sha256:bc0eb0af5c8305486c9cb00fdaa68c43d3207bc0906f5976bf0dc26762d199de'
---

# `secure-storage-performance-hardening` plan

## Description

## Steps

## Wave `W01` - Measure and classify the complete surface

Establish a reproducible, non-frozen census and attribution baseline for every CLI node before changing loading or storage behavior.

### Phase `W01.P01` - Live command census and capability contract

Make the real installed command tree authoritative for universal enrollment.

- [ ] `W01.P01.S01` - Extend the live command walker to emit stable command paths, node kind, loader owner, and handler owner for every reachable node; `src/cadrumo/entrypoints/cli/_command_suggestions.py`.
- [ ] `W01.P01.S02` - Define command capability classes covering registry, profile custody, encrypted facts, network, browser, Google, calculation, filing, and state-free behavior; `src/cadrumo/entrypoints/cli/_command_schema.py`.
- [ ] `W01.P01.S03` - Derive declared command risk and capability expectations from the live command authority instead of a second verb inventory; `src/cadrumo/tests/declared_command_risk.py`.
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

### Phase `W03.P07` - Public summary inventory

Expose the minimum authenticated discovery projection.


### Phase `W03.P08` - Single-pass CLI consumption

Join active state once and render without re-entering persistence.


## Wave `W04` - Enforce universal responsiveness and robustness

Turn the architectural properties into permanent gates over every CLI node and ratchet all observed outliers.

### Phase `W04.P09` - Whole-tree import and capability gates

Prove each live node resolution graph is a subset of its declared capabilities.


### Phase `W04.P10` - Whole-tree latency, scaling, and side-effect gates

Hold every enrolled node to calibrated class budgets.


## Wave `W05` - Integrate, audit, and close

Validate the refactor against all behavior, security, architecture, and campaign-level completion criteria.

### Phase `W05.P11` - Regression and security convergence

Preserve CLI schemas, refusal semantics, custody guarantees, and storage roundtrips.


### Phase `W05.P12` - Independent closure

Prove the entire live CLI and secure-storage goal is satisfied.


## Parallelization

## Verification
