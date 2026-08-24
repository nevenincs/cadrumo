---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cae09a27cf0dbf511892615ed5012ccc74936de5c1956801135692aa11ccdc8f'
step_id: 'S38'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove dry-run parity, committed-unit accounting, child provenance references, unsupported cancellation and deadline claims, and cleanup before settlement

## Scope

- `src/cadrumo/application/live/tests/test_filed_history_operation.py`
- `src/cadrumo/application/operations/tests/test_supervisor.py`
- `src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py`
- `.vault/index/tui-architecture.index.md`

## Description

- Consolidate the filed-history executor and facade proofs into the plan-owned canonical test module.
- Delete the two fragmented predecessor test modules without a shim, forwarding import, or duplicate copy.
- Exercise the registered definition through the production supervisor, filesystem journal, filesystem lease repository, encrypted secure-reference repository, and encrypted sync-run repository.
- Assert dry-run discovery-unit parity and effect `NONE`, committed-unit `UPDATED` and `PARTIAL` accounting, and a resolvable domain-owned sync-run reference.
- Assert cancellation is refused, execution and cleanup deadlines remain absent, and the cleanup phase precedes the operation settlement phase.
- Retain public-facade origin, privacy, uniqueness, resolution, and lazy-import proofs in the same canonical home.
- Prove the generic supervisor consumes returned domain references on initial and resumed execution while preserving the existing `None`-return/manual-settlement contract.

## Outcome

The filed-history operation now has one test owner at `src/cadrumo/application/live/tests/test_filed_history_operation.py`. The prior executor and facade modules were removed rather than bridged. The canonical suite proves the operation declaration and durable runtime agree that cancellation is unsupported and no deadline exists, preview and normal execution walk the same fixture-backed production discovery unit while preview records no unknown effect, and cleanup is durably ordered before settlement.

The completed-run child reference is produced by the canonical sync-run writer, resolves through the real encrypted repository to the exact stored record, and is the same reference returned by the filed-history result boundary. The production supervisor consumes that return, closes owned resources before terminal persistence, records the same reference in the successful receipt and terminal event, reloads the identical terminal snapshot, and releases the exact conflict lease. The same generic join now has direct and resumed-executor regressions; executors returning `None` retain explicit settlement semantics.

Committed reference accounting settles `UPDATED`, while the same committed result plus a scoped stage failure settles `PARTIAL`; refusal-only and dry-run results settle `NONE`.

Focused Ruff, BasedPyright, collection, the thirteen-test canonical module, and the sixty-three-test operation/supervisor integration surface pass. The feature-scoped vault check passes without warnings after CLI-owned annotation cleanup, body re-attestation, and feature-index regeneration. The execution record was scaffolded through `vaultspec-core`; the coordinator-owned plan checkbox was intentionally not mutated.

## Notes

The first focused run exposed that an inspected snapshot retains only its latest committed event batch. The proof was corrected to replay the authoritative durable event stream before asserting whole-operation parity. An attempted routed-browser composition was removed after a bounded timeout showed Playwright could not reap reliably during event-loop teardown in the shared high-load Windows worker; the accepted deterministic seam instead runs the canonical encrypted sync-run writer inside the real filed-history executor and supervisor, while existing adapter-owner suites retain real browser/session coverage. No mock, monkeypatch, skip, xfail, compatibility bridge, or alternate test home was added.
