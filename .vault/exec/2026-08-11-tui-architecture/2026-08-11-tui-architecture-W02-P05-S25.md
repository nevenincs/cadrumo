---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7bb64b9e77738af80247587b6b4841531f5f5d6e3cbb526e7e291645da964fd3'
step_id: 'S25'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Normalize expected refusals and unexpected failures into safe terminal diagnostics while retaining correlation evidence

## Scope

- `src/cadrumo/application/operations/_supervisor.py`

## Description

- Move `OperationDiagnosticReference` to the operation model boundary so terminal receipts and ordered events validate the same opaque fingerprint shape.
- Normalize a registered executor error in the `REFUSED` category to a terminal `REFUSED` receipt carrying only its canonical registry code.
- Normalize every other executor exception to a terminal `FAILED` receipt with a SHA-256 correlation reference over operation id, definition id, fully qualified exception type, and terminal revision.
- Append the diagnostic event and terminal event in the same durable transition, preserving the prior effect and existing cleanup-before-settlement rule.
- Prove the paths through a real encrypted operand store, filesystem journal, lease repository, and closeable resource.
- Prove registered errors outside the canonical `REFUSED` category fail closed with the same safe opaque diagnostic path, and cancellation crosses the executor boundary without an invented terminal artifact before controlled settlement.

## Outcome

Registered refusals never persist their message, arguments, context, or traceback; the receipt carries the registered refusal code. Unexpected executor failures preserve the already-recorded effect and settle only after owned cleanup, with the same opaque correlation reference in the terminal diagnostic event and receipt.

The unexpected-failure reference intentionally correlates one fully qualified exception type at one operation terminal revision. It is not a message fingerprint, so it cannot correlate arbitrary exceptions with the same type across operation identities and cannot reveal an operand, exception detail, URL, filesystem path, or secret.

Final independent S25 verification on the live shared tree:

- `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_supervisor.py -q -m integration` - `32 passed in 22.31s`.
- `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_models.py src/cadrumo/application/operations/tests/test_events.py -q -m unit` - `36 passed in 5.40s`.
- Scoped Ruff check and format check passed for the three production modules and two direct test modules; scoped BasedPyright reported `0 errors, 0 warnings, 0 notes`.
- The full-tree `uv run --no-sync basedpyright` exit was `1` with 16 residual errors only in foreign shared-worktree paths: `application/modelo/_export.py`, `application/user_profile/_custody_hold_models.py`, `domain/calculations/registry/_loader.py`, and `_loader_fingerprints.py`. No S25 path was reported.
- Scoped `git diff --check` passed.
- Post-close `uvx vaultspec-core vault check all` exited `0` and reported `Your vault is clean`; it retained 1320 global warnings in unrelated historical and concurrent vault artifacts. No S25 exec, audit, or plan warning was reported.
- The independent `2026-08-14-tui-architecture-s25-review-audit` final re-review is `PASS`.

## Notes

The semantic RAG service was unavailable because its GPU service environment could not start; grounding used the live plan row, accepted decision and research, whole operation source contracts, core error registry, observability/redaction/fingerprint authorities, and targeted duplicate confirmation.

The final supervisor proofs cover a naturally constructible registered core `ERROR` as `FAILED`, never `REFUSED`, and cancellation of `OperationSupervisor.start`: `CancelledError` propagates, emits neither diagnostic nor terminal journal event, stores no receipt, and permits subsequent explicit cleanup settlement of the owned asynchronous resource.

`W02.P05.S25` was closed through `vaultspec-core vault plan step check`. This record does not assert S26 startup reconciliation or S27 exhaustive lifecycle coverage.
