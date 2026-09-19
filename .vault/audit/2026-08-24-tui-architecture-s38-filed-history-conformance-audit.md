---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:99ac7817c0fdd055bf451707cf2499e3fb7f43365afba3c606061bd8fb309493'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S38 filed-history conformance review`

## Scope

Independent review of `W03.P07.S38` against the accepted operation-supervisor and filed-history clauses in the TUI architecture ADR, its grounding research, the implementation plan, and the S38 execution record. The review covered returned-reference propagation on initial and resumed execution, preservation of the returned-`None` manual-settlement contract, encrypted `SyncRunRecord` identity, terminal receipt and event durability, effect truth, cleanup ordering, lease release, cancellation and deadline declarations, dry-run parity and provenance, test topology, and the prohibition on mocks, fakes, patches, skips, and xfails.

The stabilized final re-read inspected `HEAD` `dc624bdf8fb7bebe59ec6eeec1cd730a87597613` plus the S38 test-topology consolidation in the shared worktree. The two real routed-browser branches passed in 65.28 seconds, the remaining thirteen canonical tests passed in 40.32 seconds, and the fifty generic supervisor tests passed in 45.29 seconds. All 65 tests collect cleanly. Ruff and BasedPyright pass on the reviewed production and test files.

## Findings

### none-reference-settlement | critical | Dry runs and other no-provenance outcomes remain running and retain their lease

`FiledHistoryOperationExecutor.execute` returns only `_result_reference(run)`, and that helper returns `run.sync_run_ref`. A dry run correctly creates no sync-run provenance, so the executor necessarily returns `None`; the same happens on other legitimate no-provenance exits such as discovery finding no pair. The generic supervisor deliberately preserves backward-compatible manual settlement when an executor returns `None`: `_settle_returned_result` returns the running snapshot unchanged. The filed-history executor performs no manual settlement. Consequently `OperationSupervisor.start` returns a nonterminal `RUNNING` snapshot, no terminal receipt or terminal event is persisted, and the exact conflict lease is not released. The canonical zero-effect test explicitly accepts `RUNNING`, while the dry-run test omits lifecycle, terminal, and lease assertions. This violates the accepted dry-run, settlement, durable identity, cleanup, and exact lease-release contracts.

Current-tree resolution: the coordinator added `_settlement_reference`, which retains the exact child sync-run reference when one exists and otherwise persists the typed `FiledHistoryOnboardingRun` behind the encrypted operation result store. Dry-run and empty/no-provenance results now settle terminally, reload through a resolvable result reference, and release their lease, while the generic returned-`None` contract remains unchanged. The current canonical tests prove both terminal branches. This critical finding is resolved in the in-progress working tree.

### real-behavior-seam | high | The canonical acceptance proof replaces the composed production path

`src/cadrumo/application/live/tests/test_filed_history_operation.py` supplies `_FixtureBackedFiledHistoryDiscovery`, `_local_pull`, and an inline `persisted_pull` in place of the registered definition's production pull. The terminal-reference proof calls the private `_persisted_bulk_filed_capture_report` writer directly and returns a constructed `FiledHistoryOnboardingRun`; it therefore bypasses the production `pull_filed_history` stage composition. This violates the explicit no-fakes or stubs acceptance rule and permits the suite to pass while composition, stage joins, production cleanup, or provenance handoff is broken. A writer-backed callable is useful as a narrow writer/reference unit proof, but it cannot serve as the composed-operation acceptance proof.

Current-tree re-read: the direct private writer and inline `persisted_pull` were removed, and the production `pull_filed_history` composition now accepts and forwards the existing register seam. The replacement `_DeterministicEmptyRegister` still skips `DeclaracionesRegisterSession.__init__` and overrides `walk` to return a canned empty tuple. It is a test-only fake of the outbound adapter despite inheriting its production class. The HIGH finding therefore remains open under the explicit no-fakes or stubs rule.

Stabilized resolution: `_DeterministicEmptyRegister` was deleted. The canonical S38 dry-run and committed-child branches now construct an actual `AeatSession`, Playwright browser, browser context, page, and `DeclaracionesRegisterSession`; only external HTTP response bytes are routed to canonical local HTML. Both branches execute the production `pull_filed_history` composition through discovery, pair walking, declaration capture or preview, result construction, normal browser teardown, supervisor settlement, and lease release. No mock, fake, patch, skip, or xfail construct remains. Routed-browser support duplicated across three test modules was consolidated into the single `src/cadrumo/tests/offline_aeat_register.py` owner. This HIGH finding is resolved.

### dry-run-provenance-proof | medium | S38 does not prove the encrypted sync-run namespace stays untouched

The canonical S38 dry-run test proves effect `NONE`, absence of an `UNKNOWN` effect event, and pair-progress parity. It does not assert `result_ref` absence, inspect the encrypted sync-run namespace, or compare encrypted storage before and after preview. Other live tests establish an absent returned sync reference and byte identity for the observation-store absorb path, but neither assertion proves that the S38 registered operation wrote no `SyncRunRecord`. The acceptance claim is therefore broader than the evidence.

Stabilized resolution: the dry-run branch now records the real encrypted sync-run namespace payload hashes before and after execution and asserts both are the empty mapping. The committed-child branch is the positive control: it asserts non-empty encrypted namespace payload hashes, resolves the terminal receipt's exact reference through `SyncRunRecordRepository`, and proves the repository-derived identifier and bucket identity match. This MEDIUM finding is resolved.

No fragmentation finding was found: `test_filed_history_operation_executor.py` was atomically renamed to the canonical `test_filed_history_operation.py`, `test_filed_history_operation_facade.py` was deleted, no compatibility module or forwarding import remains, and targeted discovery found only the canonical test home. Generic returned-reference propagation is implemented for both `start` and resumed execution, the generic supervisor tests preserve returned-`None` manual settlement, and the current filed-history working tree no longer depends on that manual path for a valid result.

The final topology also merges and deletes `test_filed_history_composition.py`; its discovery-scope, refusal-join, dry-run parity, and empty-discovery proofs now live in `test_filed_history_operation.py`. There is no shim, forwarding import, re-export bridge, or duplicate test implementation at the former executor, facade, or composition homes.

## Recommendations

**Recommendation: PASS `W03.P07.S38`.** All CRITICAL, HIGH, and MEDIUM findings are resolved in the stabilized tree, the canonical test topology has one home, and fresh real-behavior and generic supervisor gates are green.

For `none-reference-settlement`, give every successful filed-history outcome a domain-owned resolvable result reference or explicitly settle no-provenance outcomes through the supervisor contract. Preserve the generic returned-`None` manual-settlement behavior for existing executors. Add real-journal assertions that dry-run and empty-discovery outcomes become terminal, reload identically, emit the same receipt in the terminal event, and release the exact lease.

For `real-behavior-seam`, retain a direct writer proof only as a narrow encrypted-reference test. Exercise the registered operation through the real `pull_filed_history` composition using the narrowest deterministic production adapter seam. If local register data is required, thread the existing `capture_filed_data_bulk(register=...)` seam through `_capture_discovered_filed_history` and `pull_filed_history` and supply a real `DeclaracionesRegisterSession`; browser lifecycle may remain in the adapter-owner suites, but the S38 proof must not replace the application composition with a `pull=` test callable.

For `dry-run-provenance-proof`, compare the real encrypted sync-run namespace before and after the registered dry run, with a positive-control committed run proving the observation can detect a write. Assert the dry-run terminal receipt references a domain-owned non-provenance result rather than a `SyncRunRecord`.

All three recommendations are implemented and verified by the stabilized gates recorded above.
