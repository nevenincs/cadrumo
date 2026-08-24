---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:13c869352809116804c377f1fa08c81ca12ae6ef1aadd4b912f9d2a95e630839'
step_id: 'S38'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove dry-run parity, committed-unit accounting, child provenance references, unsupported cancellation and deadline claims, and cleanup before settlement

## Scope

- `src/cadrumo/application/live/tests/test_filed_history_operation.py`
- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/live/_filed_history_operation.py`
- `src/cadrumo/tests/offline_aeat_register.py`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_walk_offline.py`
- `src/cadrumo/application/live/tests/test_filed_bulk_sweep_continues_past_a_failed_pair.py`
- `src/cadrumo/application/live/tests/test_filed_bulk_capture_continues_past_a_failed_pair.py`
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

The filed-history operation now has one test owner at `src/cadrumo/application/live/tests/test_filed_history_operation.py`. The prior executor, facade, and composition modules were removed rather than bridged. The canonical suite proves the operation declaration and durable runtime agree that cancellation is unsupported and no deadline exists, preview and normal execution walk the same locally routed real `AeatSession`/Page/Context/`DeclaracionesRegisterSession` composition while preview records no unknown effect, and cleanup is durably ordered before settlement.

The completed-run child reference is produced by the canonical sync-run writer, resolves through the real encrypted repository to the exact stored record, and is the same reference returned by the filed-history result boundary. The production supervisor consumes that return, closes owned resources before terminal persistence, records the same reference in the successful receipt and terminal event, reloads the identical terminal snapshot, and releases the exact conflict lease. The same generic join now has direct and resumed-executor regressions; executors returning `None` retain explicit settlement semantics.

Committed reference accounting settles `UPDATED`, while the same committed result plus a scoped stage failure settles `PARTIAL`; refusal-only and dry-run results settle `NONE`. When no child sync-run provenance exists, the executor persists the typed `FiledHistoryOnboardingRun` through encrypted operation operands so the generic supervisor can settle terminally without inventing a child reference. The dry-run proof byte-compares the sync-run namespace payload inventory before and after as exactly empty; the normal positive control proves that namespace is non-empty and resolves the receipt's exact encrypted child record.

Focused Ruff and BasedPyright pass, the fifteen-test canonical module passes in 68.65 seconds, the four consolidated adapter-owner routed-browser tests pass in 67.62 seconds, and the fifty-test generic supervisor surface passes in 39.38 seconds. Every Playwright context and pytest process exits normally. The execution record was scaffolded through `vaultspec-core`; the coordinator-owned plan checkbox was intentionally not mutated.

## Notes

The first focused run exposed that an inspected snapshot retains only its latest committed event batch. The proof was corrected to replay the authoritative durable event stream before asserting whole-operation parity. A later high-load routed-browser run stalled during Proactor cancellation; consolidating the duplicated offline route/session helpers exposed a `slots=True` callback incompatibility, which was removed, and repeated bounded real-browser runs now close normally. One canonical support module now owns fixture loading, pager inspection, certificate-session construction, route sequencing, and browser cleanup for the adapter, listing, capture, and operation proofs. No mock, monkeypatch, fake register, skip, xfail, compatibility bridge, or alternate filed-history test home remains.
