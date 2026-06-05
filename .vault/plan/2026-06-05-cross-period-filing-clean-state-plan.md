---
tags:
  - '#plan'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
tier: L2
related:
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
  - '[[2026-06-05-cross-period-calculation-guards-research]]'
  - '[[2026-06-05-cross-period-calculation-guards-reference]]'
---


<!-- RETIRED: S03, S04, S05, S07, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20 -->

# `cross-period-filing-clean-state` implementation plan

### Phase `P01` - define dependency proof contract

Define the application-level proof model and repository joins that classify cross-period dependencies as clean or blocking.


Implement a uniform clean-state proof for filing-grade cross-period modelo dependencies.

- [x] `P01.S01` - Add clean-state proof model and resolver service; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `P01.S02` - Expose clean-state proof interfaces through calculation exports; `src/aeat/application/calculations/__init__.py`.

### Phase `P04` - wire filing-grade enforcement

Wire the clean-state proof into calculation, verification, export, and filing boundaries without weakening permissive preview behavior.

- [x] `P04.S06` - Wire clean-state blocking into modelo verification and filing; `src/aeat/application/modelo/_actions.py`.
- [x] `P04.S08` - Gate export on clean-state dependency proof; `src/aeat/application/modelo/_export.py`.

### Phase `P02` - cover state matrix with real tests

Add real-behavior tests for complete, missing, stale, superseded, local-only, AEAT-attested, divergent, and group-incomplete dependency states.

- [x] `P02.S21` - Cover clean-state proof with real repository tests; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [x] `P02.S22` - Cover filing-grade gates with real workflow tests; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

### Phase `P03` - run focused quality gates

Run focused validation for the changed application, domain, and test surfaces and record any remaining risk.

- [x] `P03.S23` - Run calculation proof tests; `src/aeat/application/calculations/tests`.
- [x] `P03.S24` - Run modelo workflow gate tests; `src/aeat/application/modelo/tests`.
- [x] `P03.S25` - Run plan validation and style checks; `quality gates`.

## Description

This plan turns the accepted clean-state ADR into an application-layer enforcement
path. It preserves permissive prefill behavior for explicit diagnostic preview, but
requires proof-backed upstream filing state before cross-period values can support
verification, export, readiness, or filing.

## Steps

## Parallelization

The proof model and repository discovery steps can proceed in parallel with test
fixture inspection. Enforcement wiring depends on the proof service contract. Export
and filing gates depend on verification findings so the same verdict is reported
consistently.

## Verification

The plan is complete when the proof service, calculation or verification wiring,
export and filing gates, and real-behavior tests all pass focused quality gates without
using fakes, mocks, stubs, monkeypatches, skips, or xfails.
