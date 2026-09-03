---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e818c5ce5b3769d49aeac0941e6c724258cf8c20684d21b822c422243578198c'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P28.S383 Review`

## Scope

Reviewed the approved S383 outcome and commits `a5f8341ec1`, `7e92a12195`, and `b480e91e1b` against the governing plan, navigation ADR, product research, Step Record, root composition, and focused tests. The audit covered destination-stack ownership, account/session rendering, semantic focus, Home refresh, application-boundary injection, search wiring, type and lint gates, and targeted duplication evidence.

Re-reviewed the remediation in `814c50cec9` over `0c9f7537e4..814c50cec9`. Focused tests passed: 17 tests. Ruff, ty, and basedpyright passed. The targeted duplication scan found no clones.

## Findings

### destination-return-and-focus | high | A completed child journey cannot refresh Home or restore a semantic Home target

The original root only reacted to `HomeBackRequested`, which is emitted by the Home screen itself for Escape. It pushed a destination without a completion result or callback, so a child dismissal returned to the bare root rather than a newly projected Home. In addition, `_show_home` accepted a focus identity but never consumed it when creating Home.

Resolved in `814c50cec9`: a child is pushed with the root completion callback, which refreshes Home through the injected projection door. The remembered `HomeTarget` is passed as the Home restore target. The focused integration test selects a real Home target, mounts a child, dismisses it through Textual, and verifies the returned Home highlights that same semantic target.

### expired-session-admission | high | Expiry does not change the active destination policy

The original expired and non-expired branches of `_show_home` performed the same replacement, and `navigate_to` admitted every catalogue target without considering the refreshed session posture.

Resolved in `814c50cec9`: refresh of an expired projection derives a closed catalogue that retains Home but locks each non-Home route with `session.expired` and no factory. The focused integration test makes a real child return into expiry, verifies the account/header and locked admission, and proves a later non-Home navigation raises before a factory is invoked.

## Recommendations

No blocking follow-up is required for S383. Preserve the real-dismissal and expired-admission integration tests when S384 supplies production factories; the root must remain limited to injected projections, catalogue admission, and screen lifecycle.
