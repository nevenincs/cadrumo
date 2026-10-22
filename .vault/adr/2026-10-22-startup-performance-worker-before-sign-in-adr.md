---
tags:
  - '#adr'
  - '#startup-performance'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:568df596ace2e138e002dcbf89c0bb4512029553b6a6f62cce07c1605159f7cd'
related:
  - "[[2026-10-22-startup-performance-request-path-audit]]"
  - "[[2026-10-16-idle-churn-adr]]"
---

# `startup-performance` adr: `A watched profile's worker starts before its sign-in` | (**status:** `accepted`)

## Problem Statement

A sign-in starts the profile's worker: the runtime launches an isolated interpreter, waits for it to import and connect, and only then derives the key. On the measured package copy that launch was about 1.9 s of a 5.1 s sign-in, and more on the operator's loaded host (`2026-10-22-startup-performance-request-path-audit`, finding worker-cold-first-operation). The desktop's `session watch` child reads the selected profile's sign-in status from the moment the window opens, usually long before the password is typed.

## Considerations

- A host keeps one worker per profile and reuses it across sign-ins; only the first custody request constructs it (`src/cadrumo_runtime/host/session_owner.py`).
- The worker is bound at launch to public custody coordinates (profile, installation, custody generation, DEK epoch) and holds no key until a sign-in installs one under the runtime's admission.
- Watch requests come only from verified same-owner peers (`src/cadrumo_runtime/host/profile_connection_sessions.py`).
- The KDF child is already started ahead of its use.

## Considered options

- **A generic pre-started worker bound at sign-in.** Hides the launch for any profile, but needs a new handover of identity, environment and endpoints into a running process. Rejected for now as a larger change to worker identity.
- **Start the watched profile's worker when its signed-out status is watched.** No protocol or identity change; the worker the sign-in would build is built earlier. Chosen.

## Constraints

- Only a watched status read of a signed-out profile, from a verified same-owner peer, starts the worker, once per profile host, in the background; the reply never waits for it.
- The early worker holds no key, lease or session. Admission, KDF, receipt and every later check are unchanged.
- A sign-in that arrives while the worker is still being built waits for that worker, bounded, instead of building a second one or being refused. A request made under the profile fence is still refused during construction.
- A failed early start leaves the sign-in to start the worker, as before, and a later watch may try again.
- `SignInStatusRequest` no longer promises that a watched read opens no worker.

## Implementation

`ProfileWorkerSessionOwner.prepare` constructs the worker key-free; `RuntimeProfileConnections.prepare_for_sign_in` runs it in a thread when a watched read finds the profile signed out; human authentication waits on a construction in progress.

## Rationale

The worker a sign-in needs is fully determined before the password exists, and the window announces the profile it will sign in to. Building it then moves the slowest step of sign-in into time the person spends typing, without changing what the worker may do or when it receives a key.

## Consequences

- A signed-out window keeps one idle worker process for its selected profile.
- Sign-in on the measured copy falls from 5.1 s to 2.8 s; the first operation after it no longer pays the launch.
- Tests cover a sign-in meeting a pending construction and a preparation that runs once and is retried after a failure.

Accepted 2026-10-22 under the operator's instruction in this session: "fix the roots causes. if you have to refactor everything." The operator did not answer the follow-up question offering a pre-started worker within five minutes; it is recorded as accepted on that instruction and is open to the operator's veto.
