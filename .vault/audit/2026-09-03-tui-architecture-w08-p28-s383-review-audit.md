---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:d942fb67f92a6590d84a5a9382763d6d5ba528be9ba0fdb04b984681cf4559a2'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P28.S383 Review`

## Scope

Reviewed the approved S383 outcome and commits `a5f8341ec1`, `7e92a12195`, and `b480e91e1b` against the governing plan, navigation ADR, product research, Step Record, root composition, and focused tests. The audit covered destination-stack ownership, account/session rendering, semantic focus, Home refresh, application-boundary injection, search wiring, type and lint gates, and targeted duplication evidence.

Focused tests passed: 17 tests. Ruff, ty, and basedpyright passed. The targeted duplication scan found no clones.

## Findings

### destination-return-and-focus | high | A completed child journey cannot refresh Home or restore a semantic Home target

The root only reacts to `HomeBackRequested`, which is emitted by the Home screen itself for Escape. It pushes a destination without a completion result or callback, so a child dismissal returns to the bare root rather than a newly projected Home. In addition, `_show_home` accepts a focus identity but never consumes it when creating Home. The existing test invokes the Home event directly and therefore does not demonstrate a real child return, projection refresh, or restored semantic focus.

### expired-session-admission | high | Expiry does not change the active destination policy

The expired and non-expired branches of `_show_home` perform the same replacement, and `navigate_to` admits every catalogue target without considering the refreshed session posture. An expired projection can therefore still navigate to a non-Home destination. This does not implement the planned session-expiry behavior or make the destination stack reflect application-owned admission.

## Recommendations

1. Define a typed, frontend-neutral child completion/back result that the root handles by obtaining a fresh Home projection, replacing the child with Home, and passing the returned Home semantic target into the Home screen. Add an integration test that dismisses a real child route and proves one refresh, one Home screen, and focus on the initiating Home target.
2. On a refreshed expired session, retire any active child and apply application-owned destination admission before invoking a factory; keep the root as a projection consumer. Add an integration test that an expired session cannot invoke a non-Home factory and remains on the appropriate refreshed Home/account state.
3. Retain the passing static gates and add the two journey-level tests above; direct invocation of the Home event is insufficient coverage for this root contract.
