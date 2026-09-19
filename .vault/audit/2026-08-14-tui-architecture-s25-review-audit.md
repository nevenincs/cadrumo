---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:4ed4816a7148b285f6a3a5727f2e87fecdfa7cfa608c4037955fef23ee57c7b7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
---
# `tui-architecture` audit: `S25 failure normalization and diagnostic correlation review`

## Scope

Independent formal review of exactly `W02.P05.S25` against the live open plan row, accepted TUI architecture ADR and research, S24 and S25 execution records, the final S24 review settlement, the current diff from `HEAD`, and the whole changed operation production and test surface. The review traced the canonical error registry, hashing, redaction, observability, journal atomicity, event, receipt, cleanup, effect, and cancellation authorities. It excluded unrelated shared-worktree changes and makes no S26 startup-reconciliation or S27 exhaustive-lifecycle claim.

The semantic RAG service had an empty local index and the user explicitly waived offline RAG for this review. Direct source and exact-symbol confirmation were therefore the evidence boundary.

## Findings

### registered-non-refusal-proof | medium | The registered non-REFUSED classification branch is not exercised through the production supervisor

`OperationSupervisor._settle_executor_failure` currently does the right thing: exact registry lookup maps only `ErrorCategory.REFUSED` to terminal `REFUSED`, while a registered `FAIL`, `ERROR`, `AUTH`, `INTEGRITY`, `INTERNAL`, or `LOCKED` error reaches `FAILED`. The real integration coverage proves one registered `REFUSED` error and one unregistered `RuntimeError`, but it never raises a registered non-`REFUSED` error through `start`. A mutation that changes the predicate from registered-and-REFUSED to merely registered would make registered failures appear as operator refusals while all current S25 tests remain green. The review's direct registry probe confirmed `AuthorizationManifestError` is registered as `FAIL`, but that read-only probe is not a production test gate.

### asyncio-cancellation-proof | medium | Cancellation propagation across the new catch boundary has no real-behavior regression test

The production branch catches `Exception`, and the installed runtime confirms `asyncio.CancelledError` is not an `Exception`, so cancellation currently propagates rather than being normalized to terminal `FAILED`. Existing cancellation tests exercise executor-owned cancellation handling, `await_terminal` cancellation, and the cooperative request protocol, but none cancels the task executing `OperationSupervisor.start` at the new `try` boundary and proves that no diagnostic or terminal transition is manufactured. A future broadening to `BaseException` would swallow asynchronous cancellation and all current S25-focused tests would still pass.

The remaining reviewed behavior is sound within S25's boundary. Unregistered exceptions fail closed to `FAILED`; registered refusals persist only the canonical registry code; the SHA-256 correlation payload contains operation id, definition id, fully qualified exception type, schema marker, and terminal revision but no exception message, arguments, context, traceback, path, URL, or secret; the digest uses the canonical core hashing primitive; `OperationDiagnosticReference` has one definition at the operation model boundary and both receipts and events consume that alias; the journal atomically commits the diagnostic event, terminal event, and receipt; the prior effect is preserved; and terminal publication remains gated by S24 executor-stop and cleanup settlement. The S25 execution record truthfully leaves the plan row open and disclaims S26 and S27.

Focused validation passed 30 real supervisor integration tests and 36 model/event unit tests. Scoped Ruff check and format check passed; BasedPyright reported zero errors, warnings, or notes. The installed runtime probe confirmed cancellation inheritance, exact registered refusal categorization, exact registered non-refusal categorization, and fail-closed unregistered lookup.

## Recommendations

1. Add a concrete executor that raises a real registered non-`REFUSED` `CadrumoError` through `OperationSupervisor.start`; assert terminal `FAILED`, an opaque diagnostic reference, no refusal reference, cleanup completion, and absence of planted sensitive exception data from both typed snapshots and durable bytes.
2. Add a real asynchronous executor that blocks after start, cancel the task awaiting `OperationSupervisor.start`, and assert `asyncio.CancelledError` propagates while the journal contains no diagnostic or terminal event and no terminal receipt. Keep subsequent lifecycle disposition outside S25 unless it is proven through the already-authorized S24 or S26 contract.
3. Re-run the 30 supervisor integration tests, 36 model/event unit tests, scoped Ruff check and format check, BasedPyright, and VaultSpec validation after remediation.
## Final re-review

PASS. Both original MEDIUM findings are resolved, and the final review found no remaining correctness, safety, diagnostic-authority, redaction, atomicity, cleanup, effect, scope, or test-quality findings within `W02.P05.S25`.

`registered-non-refusal-proof` is resolved. `RegisteredErrorExecutor` raises the real registered `CoreError` through `OperationSupervisor.start`. The test proves the registry row is `ERROR_CADRUMO_CORE`, the terminal condition is `FAILED`, no refusal reference is present, the diagnostic and terminal events carry the same opaque SHA-256 correlation as the receipt, and planted NIF, URL, query token, filesystem path, bearer, and credential-shaped details are absent from the typed snapshot, replayed events, and all durable operation bytes.

`asyncio-cancellation-proof` is resolved. `CancellableResourceExecutor` transfers a real closeable resource to the supervisor and blocks in real asynchronous work. Cancelling the task awaiting `OperationSupervisor.start` propagates `asyncio.CancelledError`, reaches the executor, preserves the durable `RUNNING` revision with no receipt or terminal condition, and emits neither a diagnostic nor a terminal journal event. Subsequent explicit `FAILED` settlement closes the owned resource exactly once. The proof remains honest about scope: it does not classify that caller-driven cancellation as an operation cancellation and makes no S26 recovery or S27 exhaustive-terminal claim.

Final independent validation passed 32 supervisor integration tests and 36 model/event unit tests. Scoped Ruff check and format check passed; BasedPyright reported zero errors, warnings, or notes. Scoped diff hygiene passed. Targeted VaultSpec annotations, markdown, body-sections, frontmatter, placeholders, and links checks are clean, including the repaired S25 execution record. The final disposition is PASS; the plan row remains open for its authorized executor.
