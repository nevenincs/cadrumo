---
tags:
  - '#audit'
  - '#desktop-native-sign-in'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:591a139e8c6bb0f6ca579aced7a5d40c23138f38602510b0a2ab6f22d8f88e9f'
related:
  - "[[2026-10-24-desktop-native-sign-in-plan]]"
---

# `desktop-native-sign-in` audit: `Desktop native sign-in review`

## Scope

Independent plan-close review of `2026-10-24-desktop-native-sign-in-plan`, commits cfad90f29d through 931da66b20 (of 4e256a9e95 only `native/application/src/person_operations.rs` and `native/application/src/lib.rs`), against the 2026-10-24 amendments of `2026-10-04-application-sign-in-adr` and `2026-10-04-desktop-shell-adr` and the Python hold and client it replaces (`src/cadrumo_runtime/host/session_hold.py`, `session_hold_operations.py`, `src/cadrumo_client/transport/frontend_client.py`). Verdict: pass with findings; no critical or high finding. Parity confirmed for keep/end refusal semantics, key-set checks, deadlines, per-session event gating, retirement, the language cache and the receipt-resume retry and refusal map; lock order and zeroization held.

## Findings

### connection-lifecycle | medium | A protocol violation retires the session but leaves its connection open
The event router (`native/desktop/src-tauri/src/agent/person/native.rs`, `route`) stops on a push for another profile or a service-lease or model-run push and marks the session retired, but holds only the event receiver and cannot close the connection, so the runtime session lives until the last `HeldPerson` drops. The Python transport closed the connection on the same invalid frame.

### test-coverage | medium | Session-level relay and language paths are untested, and no live step drives `Person::native`
`relayed`, `relay_failed` and `language` in `native.rs` have no session-level tests (keep or end mapping, cache and dirty flag, operation cue forwarding while watching). The live proof drives `Connection` and the relay directly, so real runtime replies are not shown to pass the desktop's reply validators in `person.rs`.

### relay-parity | low | The financial-submit action lacked an error reason name
At 931da66b20 the Rust relay had no `operation_financial_submit`; 1706f66723 (another session) added it, but `person.rs` names no `person_action_operation_financial_submit` reason, so a failed financial submit loses its action in the error.

### event-subscription | low | Pushes between the login reply and the router's subscription are lost
`NativeSession::start` subscribes after `login_password` or `resume_receipt` returned; a retirement pushed in between is dropped until the next request fails.

### diagnostics | low | No slow-request or failure log replaces the hold's
The hold logged `session_hold_request_slow` and durable failure records; the native session logs neither.

### test-stability | low | Event-router tests wait a fixed 100 ms
`settle` in the `native.rs` tests sleeps instead of waiting on the event channel.

### non-windows-build | low | Constructors reachable only from Windows or test code may warn off Windows
`Person::held` and `require_held` are reached only from `#[cfg(windows)]` or `#[cfg(test)]` constructors; no non-Windows compile was run.

## Recommendations

- connection-lifecycle: let the router close the connection on a protocol violation (a `close` on the session-exchange seam, reached through a weak handle).
- test-coverage: add fake-exchange tests for the relay and language session paths; a live run through `Person::native` belongs with the packaged desktop proof, which also covers the stored desktop sign-in only the installed image may make.
- relay-parity: add the reason arm.
- event-subscription: subscribe before the login exchange and hand the receiver to the session.
- diagnostics: log the action and elapsed time of slow or failed requests through the desktop's diagnostics.
- test-stability: wait on the channel with a deadline.
- non-windows-build: gate the Windows-only constructors' helpers so a non-Windows build has no dead code.

## Resolution

Resolved in 2c3de72773, verified by `desktop-host-unit-test` (509 passed; one unrelated launcher-timing test, `agent::runner::tests::a_real_launcher_gets_the_bearer_and_stops_when_its_input_closes`, failed once under load and passed on rerun), `desktop-host-unit-clippy`, and the application crate's tests (74) and clippy.

- connection-lifecycle: fixed; the router closes the connection through the seam's new `close` on a protocol violation, tested for another profile's push and service-lease and model-run pushes.
- test-coverage: session tests added for a relayed operation and its cue, kept and ending relay refusals, a malformed relayed request, and the language paths. The live run through `Person::native` is not added: a stored desktop sign-in is admitted only from the installed desktop image, so it belongs with the packaged desktop proof, which remains open.
- relay-parity: fixed; `person_action_operation_financial_submit` named.
- event-subscription: fixed; `SignIn` subscribes before `login_password` and `resume_receipt` and hands the receiver to the session.
- diagnostics: deferred; the desktop's diagnostics are typed events with no slow-request kind, so a slow-request record needs a diagnostics schema decision.
- test-stability: fixed; the tests wait on the router with a deadline.
- non-windows-build: fixed; the Windows-only constructor helpers are gated to Windows and tests. No CI lane builds the desktop off Windows.
