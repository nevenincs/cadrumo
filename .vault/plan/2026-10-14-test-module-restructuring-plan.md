---
tags:
  - '#plan'
  - '#test-module-restructuring'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:b208cfd17cd63110448aee37ed38ba57a9dbd922a1f357b1105d4b2eb3801ff0'
---








# `test-module-restructuring` plan


## Description

Approved 2026-10-14

The user explicitly requested Luna agents at maximum reasoning to break apart and restructure the three named oversized test modules. Preserve all collected cases and existing behavior while grouping tests by their durable semantic responsibility, with every resulting module below 2,000 lines. Production behavior is outside scope.

The accepted test-topology and test-harness-sanity decisions govern S01-S03: retain domain-local ownership, canonical helper definitions, module markers, fixture visibility and lifetime, and fail-closed collection policy. This is routine restructuring within those accepted decisions and needs no new ADR.

## Steps

- [ ] `S01` - Restructure registered executor conformance tests into cohesive modules preserving collected behavior; `src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py, new sibling test/helper modules, their direct consumers under src/cadrumo/entrypoints/tests and src/cadrumo/entrypoints/runtime/tests/test_submission_stream_native.py`.
- [ ] `S02` - Restructure supervisor tests into cohesive modules preserving collected behavior; `src/cadrumo/adapters/persistence/operations/tests/test_supervisor.py and new sibling test/helper modules`.
- [ ] `S03` - Restructure profile source resolver tests into cohesive modules preserving collected behavior; `src/cadrumo/adapters/persistence/profile/tests/test_source_resolver.py and new sibling test/helper modules`.







## Parallelization

S01, S02 and S03 may execute concurrently, each owned by a distinct gpt-6-luna worker at maximum reasoning. S01 owns the entrypoints tests file and new split siblings. S02 owns operations supervisor tests and new split siblings. S03 owns profile source resolver tests and new split siblings. No worker changes ancestors, production code, shared configuration or another worker's files. Parent owns governance, integrated review, shared checks and serialized commits. Workers report exact changed paths and focused test evidence before the parent checkpoints each Step.

## Verification

For each Step, compare baseline and resulting collected test names and parametrized multiplicity, run all relocated cases, and run Ruff lint and format checks on all touched modules. Preserve assertions and test decorators, and retain fixture scope, autouse, teardown, monkeypatch targets and visibility. Check all resulting module line counts are below 2,000. Parent runs configured type and import-boundary checks once for integrated stable changes, performs bounded stale-reference and semantic ownership discovery, and records the final review. Report any existing failures distinctly and do not weaken checks or alter expectations to hide them.
