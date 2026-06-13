---
tags:
  - '#adr'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-04-12-base-module-structure-adr]]'
  - '[[2026-04-17-pytest-markers-research]]'
  - '[[2026-04-21-integration-tests-ci-research]]'
  - '[[2026-06-01-metastate-zero-tolerance-research]]'
  - '[[2026-06-04-module-test-coverage-research]]'
---

# `test-topology-refactor` adr: `hexagonal tests folders with marker-complete metadata-free suites` | (**status:** `accepted`)

## Problem Statement

The source tree currently contains test modules directly beside production modules across the package root, major architectural packages, and deep domain packages. That earlier Rust-style colocated convention made test ownership easy to infer, but it now pollutes implementation namespaces with naked `test_*.py` files and makes large-scale movement, marker audit, and duplicate-test consolidation harder to reason about.

The suite has also accumulated campaign metadata in durable test names, docstrings, comments, and inventory structures. References to vaultspec waves, phases, steps, closure IDs, and transient migration states are process artifacts, not product structure. They reduce semantic search quality and hide whether a test asserts durable behavior or merely proves that a campaign once touched a file.

This ADR records the project-wide mechanical decision for the test-location refactor. It does not change functional expectations; the purpose is topology, marker correctness, deduplication, and semantic discoverability.

## Considerations

The accepted marker implementation is not the desired vocabulary. The delivered migration must replace the current marker sprawl with a small hexagonal vocabulary aligned to the architecture boundary rule: `unit`, `integration`, `aeat_live`, `hex_domain`, `hex_application`, `hex_inbound_adapter`, `hex_outbound_adapter`, `hex_persistence_adapter`, `hex_entrypoint`, and `hex_core`. Each test module must carry exactly one execution-scope marker and at least one hexagonal layer marker.

AEAT external state-changing operations are not a test category, not a marker, and not an opt-in path. The test taxonomy must only represent allowed test surfaces. Any existing marker, hook, or documentation path that models an AEAT state-changing external test as selectable, skippable, dropped, bypassable, or otherwise representable must be removed rather than renamed.

Process and runtime-cost markers are not architectural vocabulary. Markers such as `fixture_tier_l3`, `workbook_parity`, `slow`, `inventory`, and campaign-derived selectors must be retired unless a later ADR proves that one of them represents a durable product boundary. Documentation-specific execution selectors may exist only in documentation tooling, not as general source-test architecture markers.

The prior base module structure ADR accepted colocated tests directly under packages, with examples such as `src/aeat/domain/modelos/test_smoke.py`. That decision is superseded only for the final directory shape: test ownership stays domain-local, but test files must live under a `tests/` child directory of the owning package or module boundary.

Existing marker integrity checks and pytest configuration are structural gates, but their vocabulary is part of the refactor target. This refactor must keep strict marker enforcement while replacing non-hexagonal marker names, metadata markers, and any representation of forbidden AEAT external mutation.

Pytest discovery remains anchored under `src/aeat`, but the delivered discovery pattern must be only `test_*.py`. The current `_test_*.py` pattern is a mistake to retire during this refactor. The new topology moves test files within that discovery root into domain-local `tests/` folders; it does not reintroduce a repository-root `tests/` tree.

The suite is too large to trust path movement alone. After each relocation slice, semantic verification must use the vaultspec RAG index and searches to find nearby test domains, stale duplicate assertions, and unmerged overlap.

## Constraints

Every Python test file must live under a parent directory named `tests`. A package-level test for `src/aeat/application/modelo` belongs under `src/aeat/application/modelo/tests/`. A package-root or project-structure test belongs under the nearest legitimate `tests/` harness, such as `src/aeat/tests/`, only when it is truly cross-cutting.

Every Python test module filename must start with `test_`. Leading-underscore test filenames such as `_test_*.py` and suffix-style names such as `*_test.py` are invalid final topology, even when pytest can collect them.

No new naked test files may be introduced beside production modules. A single test file still gets a `tests/` directory; small size is not an exception.

Each test module must keep exactly one execution-scope marker and at least one hexagonal layer marker at module level. Deterministic offline tests use `unit`; deterministic cross-layer tests use `integration`; allowed online tests that read from AEAT or another external service use `aeat_live` plus the owning hexagonal layer marker.

Integration-style tests that compose multiple in-process project layers must not hide behind a vague unit marker. They carry `integration` when they verify cross-layer behavior and remain offline. Integration-style tests that call an allowed online service must carry `aeat_live`; they are not allowed to hide behind `unit`.

Tests, fixtures, and helpers must not model prohibited AEAT external mutation as dormant code, opt-in code, skipped code, dropped collection items, examples, documentation snippets, or marker names. A prohibited operation is absent from the suite.

The migration must not encode campaign metadata in durable test surfaces. Test filenames, class names, function names, comments, docstrings, parameter IDs, and inventories must describe stable behavior or structural rationale, not vaultspec wave, phase, step, closure, or temporary migration bookkeeping.

The relocation must preserve import behavior without relying on fakes, stubs, mocks, monkeypatches, skips, xfails, or tautological assertions as shortcuts for a passing run.

## Implementation

The target topology is domain-local `tests/` folders. A test that asserts one package's behavior moves into that package's `tests/` directory. A test that spans several packages moves to the narrowest shared architectural owner and carries all relevant domain markers. A cross-cutting integrity gate remains in the package-level test harness only when no more specific owner exists.

The marker-integrity gate must be updated in the same migration stream so it scans the relocated files under `src/aeat`, continues to require module-level `pytestmark`, and additionally rejects any Python test file whose path lacks a `tests` segment or whose basename does not start with `test_`. During batch execution, temporary coexistence of old and new paths is allowed only inside an active, unclosed relocation slice; the closeout state has no fallback naked-test convention and no underscore-prefixed test pattern.

Markers are reassigned during movement, not after movement. Relocation work must classify the owned hexagonal boundary first, then place the test under the matching owner, then verify the module-level `pytestmark` against the new marker registry.

Allowed online and integration tests are handled as first-class slices. Google and online-call tests are not hidden under unit markers; they carry `aeat_live` or `integration` plus the appropriate hexagonal layer marker. Prohibited AEAT external mutation has no marker, no suite, and no deferred execution path.

Duplicate and overlapping tests are resolved by semantic ownership. When two tests assert the same durable behavior, the canonical version lives with the owning domain and the redundant copy is removed or narrowed to a distinct boundary assertion. The refactor is not a license to keep duplicated assertions under different paths.

Vaultspec RAG index updates and searches are required verification after relocation batches. Search terms must include the moved domain, marker class, core behavior names, and any removed transient metadata tokens so stale duplicates and orphaned references are discoverable before closeout.

## Rationale

The stricter `tests/` child-directory rule keeps the useful part of Rust-style colocation, namely local ownership, while removing namespace pollution from implementation packages. It also gives mechanical agents a clear invariant: every test file path contains a `tests` segment under its owning domain.

The existing marker taxonomy is evidence that enforcement exists, not evidence that the vocabulary is correct. The refactor uses the existing enforcement machinery but replaces the marker vocabulary with the accepted hexagonal architecture language.

The metastate-zero-tolerance research establishes that process lists and campaign labels are not durable architecture. Applying that rule to test files improves semantic search, reduces false ownership signals, and prevents future agents from treating migration bookkeeping as product behavior.

Requiring RAG-backed semantic verification acknowledges that a 30,000-plus-test suite cannot be refactored safely by filename moves alone. Semantic index refresh and search are the project mechanism for finding nearby, overlapping, or stale test intent.

## Consequences

The source tree will become quieter: implementation modules and test modules are still colocated by domain, but visually separated by `tests/` folders.

The refactor will touch many imports, pytest discovery paths, and relative fixture references. Batch sizing and disjoint ownership are therefore safety concerns, not preferences.

Historical tests whose only purpose was proving a campaign closure may disappear or be rewritten as durable structural tests. This reduces test count and maintenance cost, but it requires careful review so real behavioral coverage is not lost.

The marker-integrity gate becomes more important. Any missing, misleading, non-hexagonal, metadata, or forbidden-operation marker is a topology bug, because marker assignment is part of the relocation contract.

Future plans and execution records must treat RAG refresh and semantic duplicate search as required verification, alongside targeted pytest collection and marker-integrity checks.

The final migration must leave pytest discovery, marker hooks, coverage omit rules, and documentation pointing at one coherent topology. A partially updated discovery surface is a failed migration state, even if individual moved tests still collect.

## Codification candidates

- **Rule slug:** `tests-live-under-domain-tests-folders`.
  **Rule:** Every Python test file must live under a parent `tests/` directory at the narrowest owning package or architectural boundary; naked `test_*.py` files beside implementation modules are forbidden.

- **Rule slug:** `test-markers-are-topology-contract`.
  **Rule:** Every test module must declare exactly one execution-scope marker and at least one hexagonal layer marker at module level, using only the accepted test-marker vocabulary.

- **Rule slug:** `tests-carry-no-campaign-metastate`.
  **Rule:** Test paths, names, docstrings, comments, parameter IDs, and inventories must describe durable behavior or structural rationale, not vaultspec wave, phase, step, closure, or transient migration state.

- **Rule slug:** `test-discovery-updates-atomically`.
  **Rule:** Test relocation must update pytest discovery, marker-integrity scanning, coverage omission, and test documentation together so the project has one authoritative topology at closeout.

- **Rule slug:** `forbidden-aeat-mutation-has-no-test-marker`.
  **Rule:** Prohibited AEAT external mutation must not appear as a marker, skipped test, dropped collection item, bypass path, fixture, helper, example, or dormant test surface.

- **Rule slug:** `test-modules-use-test-prefix`.
  **Rule:** Python test modules must use `test_*.py` filenames only; `_test_*.py` and `*_test.py` patterns are forbidden.
