---
tags:
  - '#plan'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
  - '[[2026-04-17-pytest-markers-research]]'
  - '[[2026-04-21-integration-tests-ci-research]]'
  - '[[2026-06-01-metastate-zero-tolerance-research]]'
  - '[[2026-06-04-module-test-coverage-research]]'
---


# `test-topology-refactor` `execution` plan

## Description

This plan implements the accepted test topology ADR. The work is deliberately ordered so the first wave is a mechanical relocation with no test execution, followed by import and discovery repair, marker vocabulary hardening, semantic duplicate consolidation, and closeout verification.

The primary file-discovery command for the relocation inventory is `fd -t f '^test_.*\.py$' src docs -E .git -E .venv -E var`. Final topology verification uses `fd -t f '^test_.*\.py$' src docs -E .git -E .venv -E var | rg -v '(^|[\\/])tests[\\/]'`, which must return no files. Naming cleanup uses `fd -t f '(^_test_.*\.py$|.*_test\.py$)' src docs . -E .git -E .venv -E var -E docs\_build`, which must return no files.

## Steps

## Wave `W01` - mechanical topology relocation

Move test files into the narrowest owning domain tests folders without running the test suite, then prove the path invariant mechanically before semantic edits begin.

### Phase `W01.P01` - inventory current test topology

Produce the relocation inventory and log the exact fd commands used for all current test files, naked test violations, and invalid filename patterns.

- [x] `W01.P01.S01` - Log all test discovery commands and current counts; `fd inventory commands`.
- [x] `W01.P01.S02` - Write relocation ownership inventory for Spark Codecs agents; `test relocation inventory`.
- [x] `W01.P01.S03` - Record current pytest discovery and marker registry baseline; `pyproject.toml`.

### Phase `W01.P02` - move root and cross-cutting tests

Relocate package-root and project-structure tests into the narrowest legitimate tests harness before package-local slices move.

- [x] `W01.P02.S04` - Move package-root integrity tests into the central tests harness; `src/aeat/tests`.
- [x] `W01.P02.S05` - Move project-structure and locale tests into the central tests harness; `src/aeat/tests`.
- [x] `W01.P02.S06` - Rename underscore-prefixed test modules to test-prefixed modules; `src/aeat`.

### Phase `W01.P03` - move architectural package tests

Relocate naked tests owned by domain, application, adapter, entrypoint, core, locale, and setup architectural packages.

- [x] `W01.P03.S07` - Move domain-owned naked tests into domain tests folders; `src/aeat/domain`.
- [x] `W01.P03.S08` - Move application-owned naked tests into application tests folders; `src/aeat/application`.
- [x] `W01.P03.S09` - Move adapter-owned naked tests into adapter tests folders; `src/aeat/adapters`.
- [x] `W01.P03.S10` - Move entrypoint-owned naked tests into entrypoint tests folders; `src/aeat/entrypoints`.
- [x] `W01.P03.S11` - Move core and setup owned naked tests into local tests folders; `src/aeat/core`.

### Phase `W01.P04` - verify relocation mechanically

Run fd path and naming checks until no Python test file violates the tests directory or test prefix invariants.

- [x] `W01.P04.S12` - Verify no test-prefixed file remains outside a tests directory; `fd topology gate`.
- [x] `W01.P04.S13` - Verify no underscore-prefixed or suffix-style test filename remains; `fd naming gate`.
- [x] `W01.P04.S14` - Record mechanical relocation completion without running pytest; `relocation execution record`.

## Wave `W02` - import discovery and harness repair

Repair imports, discovery settings, package initializers, and collection helpers created by the relocation so pytest sees one coherent topology.

### Phase `W02.P05` - repair import and fixture paths

Update imports, relative paths, fixture lookup, resource paths, and package initializers broken by moving files into tests directories.

- [x] `W02.P05.S15` - Repair relative imports created by tests directory insertion; `src/aeat`.
- [x] `W02.P05.S16` - Repair fixture imports and conftest lookup after relocation; `src/aeat`.
- [x] `W02.P05.S17` - Repair resource paths that depended on old test module locations; `src/aeat`.

### Phase `W02.P06` - align pytest and coverage discovery

Update pytest discovery, marker integrity scans, coverage omit rules, and any collection helpers so they target only the new topology.

- [x] `W02.P06.S18` - Restrict pytest python_files discovery to test-prefixed modules; `pyproject.toml`.
- [x] `W02.P06.S19` - Update marker integrity discovery to scan relocated tests folders; `src/aeat/tests/test_marker_integrity.py`.
- [x] `W02.P06.S20` - Update coverage and test documentation topology references; `test documentation surfaces`.

## Wave `W03` - hexagonal marker standardisation

Replace legacy marker sprawl with the ADR vocabulary and make marker integrity enforce execution scope plus hexagonal ownership without forbidden mutation representations.

### Phase `W03.P07` - replace marker registry vocabulary

Replace legacy domain, runtime, inventory, parity, slow, and fixture-tier markers with the accepted execution and hexagonal marker vocabulary.

- [x] `W03.P07.S21` - Replace pytest marker registry with execution and hexagonal markers; `pyproject.toml`.
- [x] `W03.P07.S22` - Remove legacy runtime and metadata marker names; `marker registry`.
- [x] `W03.P07.S23` - Remove forbidden external mutation marker representations; `marker registry`.

### Phase `W03.P08` - harden marker integrity gates

Make integrity tests reject missing tests path segments, invalid filenames, missing module pytestmark, non-hexagonal markers, metadata markers, and any forbidden external mutation representation.

- [x] `W03.P08.S24` - Enforce exactly one execution-scope marker per test module; `src/aeat/tests/test_marker_integrity.py`.
- [x] `W03.P08.S25` - Enforce at least one hexagonal layer marker per test module; `src/aeat/tests/test_marker_integrity.py`.
- [x] `W03.P08.S26` - Enforce tests directory and test prefix topology in integrity gates; `src/aeat/tests/test_marker_integrity.py`.
- [x] `W03.P08.S27` - Reject campaign metadata and forbidden mutation tokens in test surfaces; `src/aeat/tests/test_marker_integrity.py`.

### Phase `W03.P09` - classify online and integration tests

Assign Google, online-call, integration, and offline deterministic tests to the correct execution marker and hexagonal ownership marker.

- [x] `W03.P09.S28` - Assign unit and integration markers to offline tests by behavior; `src/aeat`.
- [x] `W03.P09.S29` - Assign aeat_live markers to allowed online and Google tests; `src/aeat`.
- [x] `W03.P09.S30` - Assign hexagonal ownership markers to every relocated test module; `src/aeat`.

## Wave `W04` - metadata removal and semantic consolidation

Remove campaign metastate from durable test surfaces and use the refreshed RAG index to find duplicate or overlapping assertions by domain.

### Phase `W04.P10` - remove campaign metastate

Erase vaultspec wave, phase, step, closure, transient inventory, and migration bookkeeping terms from durable test names, comments, docstrings, parameter IDs, and inventories.

- [x] `W04.P10.S31` - Remove vaultspec wave phase step and closure tokens from test names; `src/aeat`.
- [x] `W04.P10.S32` - Remove transient inventory and migration metadata from test comments; `src/aeat`.
- [x] `W04.P10.S33` - Remove metadata-derived parameter IDs and helper names; `src/aeat`.

### Phase `W04.P11` - rag-backed duplicate consolidation

Refresh the RAG index and use semantic searches to locate overlapping tests by domain, marker, behavior, and removed metastate tokens before consolidating duplicates.

- [x] `W04.P11.S34` - Restart and index vaultspec-rag after relocation batches; `vaultspec-rag index`.
- [x] `W04.P11.S35` - Search moved domains for duplicate assertions and stale ownership; `vaultspec-rag search`.
- [x] `W04.P11.S36` - Consolidate duplicate tests into the narrowest owning domain; `src/aeat`.
- [x] `W04.P11.S37` - Record semantic search terms and consolidation decisions; `semantic verification record`.

## Wave `W05` - closeout verification and documentation

Run the final mechanical, semantic, and collection gates, update durable documentation surfaces, and record execution evidence for handoff.

### Phase `W05.P12` - run final gates

Run mechanical fd gates, marker integrity, targeted pytest collection, vaultspec-core sync checks, and vaultspec-rag index/search verification after all edits land.

- [x] `W05.P12.S38` - Run final fd topology and naming gates; `fd final gates`.
- [x] `W05.P12.S39` - Run marker integrity and pytest collection gates; `pytest collection gates`.
- [x] `W05.P12.S40` - Run vaultspec-core rule sync and status checks; `vaultspec-core sync`.
- [x] `W05.P12.S41` - Run vaultspec-rag index and semantic verification searches; `vaultspec-rag verification`.

### Phase `W05.P13` - persist closeout evidence

Update durable docs and execution records so future agents can discover the final topology, marker vocabulary, and verification commands.

- [x] `W05.P13.S42` - Update test topology documentation with approved vocabulary; `test documentation surfaces`.
- [x] `W05.P13.S43` - Persist execution summaries and closeout evidence; `.vault/exec/2026-06-05-test-topology-refactor`.
- [x] `W05.P13.S44` - Prepare final handoff with residual risk and follow-up rules; `closeout report`.
- [x] `W05.P13.S45` - Resolve resident RAG code-index jobs and rerun semantic searches; `vaultspec-rag service`.

## Parallelization

Wave `W01` is mostly parallel by architectural package once the inventory is written. Wave `W02` can run in parallel by changed import surface after relocation lands. Wave `W03` is sequenced after the marker registry is defined, but per-package marker edits can be parallelized. Wave `W04` runs after RAG indexes the moved tree so duplicate consolidation has current semantic evidence. Wave `W05` is strictly ordered because final gates depend on every earlier wave.

## Verification

The plan is complete when no Python test file under `src/aeat` is outside a `tests/` directory, no `_test_*.py` or `*_test.py` file remains, pytest discovery only targets `test_*.py`, marker integrity rejects non-hexagonal and metadata markers, RAG index and semantic searches have been run after relocation batches, and targeted collection/integrity checks pass without using skips, xfails, mocks, fakes, stubs, or monkeypatch shortcuts.
