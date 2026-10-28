---
tags:
  - '#adr'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:d0617cb950b8e267428f72b0661aa75df30b0b3bdbd788f0a4f83951e668b15b'
related:
  - "[[2026-10-28-debug-startup-reliability-audit]]"
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-10-22-startup-performance-worker-before-sign-in-adr]]"
  - "[[2026-10-22-worker-authorization-channel-adr]]"
  - "[[2026-10-13-provider-settings-adr]]"
---

# `debug-startup-reliability` adr: `Signal-driven GUI and service orchestration with emergency cutoffs only` | (**status:** `accepted`)

## Problem Statement

First login can leave the agent unavailable while independently timed components are still doing valid startup work. Increasing individual budgets does not establish a responsive orchestration contract. The first-login-phase-deadlines finding in2026-10-28-debug-startup-reliability-audit records the source trace and the user's ruling.

## Considerations

The user explicitly requires GUI and multi-service orchestration to flow through signals and slots; hard time limits are allowed only as absolute last-resort termination cutoffs. Existing idle-churn decisions already require producer-driven cues and reject holding a shared exchange slot while waiting. Exact profile/session/native-peer authority, secret custody, cancellation settlement and unknown effects remain binding.

## Considered options

- Increase each existing phase timeout. Rejected as the completed S01 mitigation leaves independent cutoffs, occupied slots and shutdown waits.
- Remove deadlines from blocking calls. Rejected because cancellation and process loss may not wake them, allowing startup owners and secrets to remain pinned.
- Correlated asynchronous readiness/admission with cancellation, free request slots and an explicit emergency watchdog. Chosen under the user's direct ruling.

## Constraints

Accepted2026-10-28 on the user's first-hand instruction: "hard timeouts must indicate absolute last resort termination cutoffs" and "everything else must be signal and slot driven". This authorization covers the scoped startup/login/service protocol corrections below, not private access beyond existing authority.

1. GUI runtime startup, first profile login, installed-service admission and hosted-agent readiness/retirement advance on identity-bound readiness, terminal completion, cancellation, peer/process exit, profile/session invalidation and available-slot signals. Ordinary phase elapsed time neither proves failure nor triggers retirement/retry. Status remains pending until evidence permits readiness or a terminal result.
2. Long preparation, verification and proof work does not occupy the GUI supervisor event loop, a shared person mutex or its request/reply slot. Start once under a correlated attempt identity, return a pending acknowledgement when work remains, cue completion, and claim the terminal result through the same exact native connection/session coordinates. A claim is observation, not mutation replay. Pending inventories and resource ownership remain bounded.
3. Cancellation, disconnect, lock, sign-out, profile switch and generation replacement invalidate the exact pending attempt. A stale completion cannot publish admission, custody, receipts, admin endpoints or gateways. Preparation and cleanup stay owned until settled. Cancellation after committed publication reports that committed result and follows existing window/session retirement rules; it does not invent rollback or retryability. No secret or private projection enters cue payloads.
4. A worker's key-free ready signal proves that its authenticated channels and dispatchers are installed. Process spawn, a listening endpoint or a prewarm thread alone is insufficient. Concurrent sign-ins join one exact construction result; they do not start another worker merely because a phase took longer.
5. Emergency waiting is a distinct neutral typed policy, with an absolute owner deadline and an explicit emergency-cutoff cause. A policy default is centralized and projected to native code; it is injectable for tests. Dependent phases consume the remaining owner budget rather than silently renewing it. Its numeric default is an implementation hypothesis, initially600seconds, and is never advertised as a normal completion target. At emergency cutoff the owner cancels, contains/reaps where required, and preserves UNKNOWN/SETTLING when effects or termination remain unproved. Forced-termination confirmation remains a separate last-resort cleanup proof.
6. Admission and disclosure still recheck exact native incarnation, profile/session/generation and scope at their existing guarded boundaries. Waiting grants no authority. Byte limits, strict framing, digest/correlation checks, lease expiries, cryptographic/KDF resource ceilings, explicit domain-operation cancellation/deadline policies and shutdown ownership remain enforced; they do not substitute for normal readiness signals.
7. GUI sign-in uses one native identity-bound path after selected/named profile resolution through current observations. A stale initial snapshot must not route the same ordinary password login through a shorter CLI helper cutoff. UI startup observations subscribe to producers and remain pending without a normal escape timer or periodic polling where producer notifications exist.

## Implementation

We will add correlated pending/terminal service and human-login contracts and completion cues, exact-attempt cancellation/claim state, and generation-tagged native preparation/admission completion messages. Native exchange-slot waits and multi-frame work respond to capacity, reply, close and cancellation signals with only the explicit emergency backstop. Runtime worker construction waits on channel readiness/child exit/owner stop and publishes dispatcher readiness. Agent controller/process waits wake on ready, refusal, EOF, cancellation or emergency; close signals them without waiting for a lifecycle lock. Emergency termination is identified in diagnostics and desktop wording. Paths and sequencing live in2026-10-28-debug-startup-reliability-plan.

## Rationale

Readiness and terminal results are facts supplied by the component that owns the work. Correlated asynchronous completion preserves those facts while keeping cancellation, profile changes and independent profile reads responsive. A separately named emergency watchdog bounds lost owners without misclassifying normal slow work. This follows the user's ruling and the existing event-driven and exact-authority decisions.

## Consequences

Neutral/native/runtime contracts change together within the package cohort. Tests must prove delay beyond former phase limits without real long sleeps, free-slot behavior, wake on cancellation/exit, no stale publication, exact-attempt proof cleanup, committed-result preservation, and emergency containment with honest unknown outcomes. Passing source tests does not prove the user's installed cold launch. General raw profile access is not added: the agent continues to receive only existing admitted typed operations/projections.

## Affected decision reconciliation

The accepted2026-10-16-idle-churn-adr is refined to make startup/login/service waiting producer-driven and emergency-only; authority and cue rules remain. The bounded construction wait in2026-10-22-startup-performance-worker-before-sign-in-adr now means an emergency backstop around a signal-joined construction, not a60-second normal refusal. The unchanged exchange-deadline wording in2026-10-22-worker-authorization-channel-adr remains for authorization permits; it grants no45-second proof/preparation or normal GUI slot-wait cutoff. Existing operation settlement and session-lifetime decisions are reused unchanged. Each affected record receives a dated scoped amendment preserving its original ruling and history.
