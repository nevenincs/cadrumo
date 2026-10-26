---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:85425adfda85355efc904bedca0ec5f9a04ee0f23a5eea3f54c7071954b8b418'
related: []
---

# `tui-architecture` audit: `s17 review`

## Scope

Independent review of `W02.P04.S17`, limited to lifecycle journal, event replay, lease, secure-reference ports, facade exposure, direct contract tests, and the shapes required by S18-S21.

## Findings

### lease-takeover-evidence | high | The lease port cannot represent the takeover evidence S19 requires

S19 explicitly owns expiry and takeover evidence, while D5 requires reconciliation to prove owner loss before replay. `acquire` returns only the new `OperationOwnerLease`; that model carries no predecessor token/owner, expired-at fact, acquisition disposition, or evidence reference. There is also no inspection or compare-and-swap acquisition result port. An adapter could take over an expired lease, but it cannot return the proof needed by the supervisor without inventing an out-of-band contract.

### replay-boundary | high | Cursor replay cannot distinguish caught-up, expired, or missing history

`OperationEventCursor` is an unconstrained `int`, and `read_after` returns only an event tuple. Empty output is therefore ambiguous between a valid caught-up cursor, expired/compacted cursor, and unknown operation; the port also has no returned next cursor or replay-bound metadata. D3 requires explicit cursor expiry and bounded replay semantics, and S21 must prove monotonic cursors and idempotent replay. The current shape cannot express those outcomes fail closed.

### protocol-test-exactness | medium | Runtime checks prove names only and do not pin callable signatures

The complete structural classes deliberately use `object` return and parameter types, which runtime-checkable protocols accept because they inspect attribute presence rather than annotations. The tests never invoke the port methods or inspect keyword-only names such as `expected_revision`, `lease`, `limit`, `expires_at`, and `operand_type`. A public callable-name regression like the one already found in S13 would remain green.

### atomic-directionality | low | Journal and secure-reference ownership are otherwise correctly separated

Commit binds snapshot and event batch to expected revision and current lease in one port call; event sequencing/timestamps remain production event facts; secure operands use canonical content digests and stay outside the credential-free journal; the lease model is frozen and validates a positive UTC window. No persistence adapter or frontend type leaks into the application boundary.

## Recommendations

- Add a closed lease-acquisition result/evidence shape that distinguishes fresh acquisition, renewal/conflict, and proved expired-owner takeover without moving reconciliation authority into the adapter.
- Replace raw cursor results with validated cursor and replay-page/outcome types that distinguish caught-up, expired, and unknown history and carry the authoritative continuation cursor.
- Pin every public port signature and exercise valid keyword calls directly through production imports; retain independent incomplete-surface refusals.
- Rerun the exact journal/facade pytest, Ruff, and basedpyright gates after remediation.

## Final re-review

### lease-result-correlation | high | Disposition presence rules do not bind predecessor and current lease evidence

The new result distinguishes lease outcomes and requires predecessor/current presence by disposition, closing the absence of an evidence channel. However, it never requires predecessor and current to name the same operation, never requires takeover to change owner/token, and never proves the predecessor was expired at `observed_at`. A `TAKEN_OVER` result can therefore combine unrelated operations or an unexpired unchanged lease and still validate. The S19 takeover/owner-loss proof remains unsound until these exact correlations are fail closed and directly mutated.

### replay-request-binding | high | A replay page is not bound to the exclusive cursor it answers

The new statuses, constrained cursor/limit, strict ordering, and final-event `next_cursor` binding resolve most of the replay finding. But `OperationReplayPage` carries no requested or starting cursor, so it cannot enforce that the first returned sequence is strictly after the caller's cursor, or that a caught-up page preserves that cursor. An adapter can answer `read_after(100)` with events 1 and 2 and return cursor 2 while the result model validates. S21's idempotent exclusive replay proof still lacks an exact request/result binding.

### protocol-test-exactness-closure | low | Invoked typed ports and signature pins close the MEDIUM finding

All port methods are invoked with production models, and keyword-bearing signatures are pinned. Independent incomplete surfaces remain refused. The recorded nine-test, Ruff, and basedpyright gates are credible for this coverage.

Final verdict: FAIL. Two HIGH findings remain; no CRITICAL or MEDIUM findings remain.

## Persisted-ordering final review

### terminal-event-order-closure | low | Terminal settlement is now the final atomic event

Terminal snapshots require exactly one terminal event and require it at `events[-1]`, with its exact receipt still bound to the persisted terminal receipt. A planted phase-after-terminal mutation is refused. The terminal-order HIGH is closed.

### phase-and-time-binding-closure | low | Persisted phase and time now derive from the ordered batch

Nonempty batches require nondecreasing UTC event timestamps and bind `updated_at` to the final event timestamp. `phase_code` equals the latest phase event, while a batch without phase events carries no phase code; `started_at` is UTC-aware and cannot follow `updated_at`. Direct tests plant phase drift, final-time drift, reversed timestamps, pre-start updates, and phase-without-event mutations. The phase/time HIGH is closed.

### ordering-gates | low | Focused implementation and test evidence is green

The execution record reports 12 direct journal tests passing, Ruff and format checks clean, and basedpyright with zero errors, warnings, or notes. Prior safe-shape, lease, replay, facade, and port invariants remain intact.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.

## Exact-correlation re-review

### lease-result-correlation-closure | low | Disposition-specific identity and timing rules close the lease HIGH

Takeover now preserves operation identity, changes both owner and token, and requires the predecessor to be expired by acquisition and observation. Renewal preserves owner/token and extends expiry; conflicts require a live current lease; expired and owner-lost outcomes require an expired predecessor. Planted identity, owner, token, and time mutations exercise the critical takeover shape.

### replay-request-binding-partial | high | Expired and compacted restart cursors may move behind the request

Pages now bind the requested cursor and require contiguous events immediately after it; caught-up and unknown outcomes preserve it. However, `EXPIRED` and `COMPACTED` only require `next_cursor == restart_cursor`. They accept `requested_cursor=100` with `restart_cursor=7`, which moves the consumer backwards and can replay already-consumed history. For these statuses the authoritative restart boundary must be strictly beyond the stale requested cursor, with a planted rollback mutation. The replay HIGH therefore remains open.

### exact-gates | low | Eleven focused tests and static gates are current

The execution record reports 11 focused tests passing plus clean Ruff and basedpyright. These gates cover the added correlations but omit the restart-cursor rollback case above.

Final verdict: FAIL. One HIGH finding remains; no CRITICAL or MEDIUM findings remain.

## Forward-only replay re-review

### replay-request-binding-closure | low | Expired and compacted restart boundaries are now forward only

The result model requires `restart_cursor` to be strictly greater than `requested_cursor` and equal `next_cursor` for both expired and compacted statuses. Planted rollback mutations cover both branches, while page continuity and caught-up preservation remain enforced. The final HIGH is closed.

The execution record reports the exact focused suite at 11 passing with Ruff clean and basedpyright at zero errors, warnings, and notes.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.

## Reopened persisted-contract review

### persisted-safe-shape | low | Schema-v1 storage separates runtime payloads from credential-free facts

The new strict frozen record carries a canonical `ContentDigest` request reference and closed lifecycle/event facts only. The journal port now loads and commits this persisted type, while the secure-reference port remains the only runtime `BaseModel` operand channel. Serialization tests prove the concrete operand value and payload/request fields are absent, and schema drift or injected runtime request data is refused.

### terminal-event-order | high | A terminal event need not be the final event in its atomic batch

Terminal persisted snapshots require exactly one terminal event and bind its receipt exactly, but validation does not require that event to be `events[-1]`. A terminal event followed by a phase, progress, log, effect, notice, or diagnostic event remains valid as long as sequences are contiguous and the cursor points at the later event. That contradicts terminal settlement finality and permits facts after the exact terminal receipt.

### phase-and-time-binding | high | Persisted snapshot phase and update time are not bound to the event batch

Event identity, revision, contiguous sequence, and final cursor are checked, but `phase_code` can disagree with the last phase event and `updated_at` can precede or otherwise disagree with the last committed event timestamp. Thus an atomic snapshot-plus-events record can persist two conflicting authoritative views of current phase/time. Direct mutations cover identity/revision/sequence/cursor and receipt, but omit phase and last-event-time drift.

### prior-invariants | low | Lease and replay protections remain intact

The earlier disposition-specific lease evidence, forward-only replay statuses, typed runtime ports, signature pins, and facade boundary remain present. Recorded focused evidence is 14 tests passing with clean Ruff and basedpyright, but it does not exercise the two exact-binding gaps above.

Final verdict: FAIL. Two HIGH findings remain; no CRITICAL or MEDIUM findings remain.
