---
name: 2026-04-17-pytest-only-testing-adr
description: Enforce one pytest-only, real-behaviour test posture with explicit execution and architecture markers
tags:
  - "#adr"
  - "#pytest-only-testing"
date: 2026-04-17
modified: '2026-07-17'
body_hash: 'sha256:1729e692970c6cae5b4897f056b42c8cda77fde501ccc85dba54f34f5aa6e22a'
related:
  - "[[2026-04-17-pytest-only-testing-research]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
  - "[[2026-06-05-test-topology-refactor-adr]]"
status: accepted
---

# pytest-only testing ADR | (**status:** `accepted`)

## Context

The test suite is an architectural proof surface. A passing result must come
from production code exercised against real objects, local processes,
authoritative fixtures, persistence, or explicitly selected external systems.
Mocks, fakes, stubs, patches, monkeypatches, skips, xfails, response recording,
global clock mutation, retries, and snapshot approval can conceal a broken
production path and therefore cannot be accepted as test-control mechanisms.

The repository also needs one execution taxonomy and one hexagonal ownership
taxonomy. Missing, mixed, or ad-hoc markers make CI coverage ambiguous.

## Decision

### Real-behaviour-only controls

- `pytest` is the only test runner.
- `unittest`, `unittest.mock`, third-party `mock`, and `pytest-mock` are
  prohibited.
- Tests must not use fake or stub implementations, patch production state,
  skip or xfail outcomes, retry failures, intercept or replay HTTP responses,
  globally alter clocks, or approve snapshots.
- Determinism comes from explicit production seams, isolated real storage,
  committed authoritative evidence, local servers and processes, and bounded
  real elapsed-time behaviour.
- Test expectations must not mirror production business logic.

The accepted pytest plugin set is limited to concrete runner capabilities:
`pytest-asyncio`, `pytest-playwright`, `pytest-xdist`, and `pytest-cov`.
Playwright fixtures are reserved for live browser tests, while deterministic
single-owner tests may launch the production browser session against owned
local resources. HTTP interception, rerun, snapshot, and clock-mutation
plugins are not dependencies.

### Marker topology

Every test module carries exactly one execution marker:

- `unit` for deterministic offline behaviour owned by one architectural
  component; owned local processes are permitted.
- `integration` for deterministic offline behaviour crossing architectural
  layers.
- `aeat_live` for explicitly selected reads from real external systems.

Every test module also carries exactly one accepted `hex_*` owner marker.
Collection and static inventory gates reject missing, mixed, per-function, or
retired marker shapes.

### Live selection

The default pytest selection is `unit`. Explicit `aeat_live` selection must
call the central prerequisite gate and fails when
`CADRUMO_LIVE_TESTS_ENABLED=1` is absent. Google live reads also require
`CADRUMO_LIVE_TESTS_GOOGLE=1`. A missing prerequisite is a failure, never a
skip.

Live-marked files receive an additional AST import check for recording,
interception, mocking, and clock-control libraries. Project-wide inventory
tests enforce the same real-behaviour posture for deterministic tests.

### Enforcement and coverage

- Ruff `TID251` rejects `unittest`, `unittest.mock`, and `mock` imports.
- Collection hooks reject execution- and architecture-marker drift before
  pytest's marker filter can hide it.
- Ratchet tests reject fake/stub classes, monkeypatching, mocks, skips,
  xfails, tautological assertions, and ungrounded calculation expectations.
- The unit coverage floor remains 60% with branch coverage enabled. It may
  only increase through a separately grounded decision.
- `src/cadrumo/tests/README.md` is the maintainer-facing operational
  reference; this ADR owns the architectural decision.

## Consequences

- A green test run represents observed production behaviour rather than a
  simulated substitute.
- External-system tests fail clearly when an operator selects them without
  satisfying prerequisites.
- Slow real browser, storage, and elapsed-time proofs remain visible costs
  instead of being hidden by test doubles or global mutation.
- Historic plans and research that authorize removed test-control plugins are
  not retained as active semantic-search material.

## Superseded details

This reconciled decision removes the original authorization for
`pytest-httpx`, `pytest-rerunfailures`, `syrupy`, `time-machine`, a `flaky`
marker, live-test skips, and fake classes. Those mechanisms conflict with the
current binding real-behaviour rules and the executable suite.
