---
tags:
  - '#audit'
  - '#dehu-notification-legal-effect'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:50f950b69a1a5ab63ead28ca743b35b18ba58bea6db3cbf0b6928040c21bea43'
related:
  - '[[2026-08-07-dehu-notification-legal-effect-plan]]'
  - '[[2026-08-07-dehu-notification-legal-effect-adr]]'
---

# `dehu-notification-legal-effect` audit: `Retire operational rows and review guarded ownership`

## Scope

The six open Phase P05 rows were reconciled against the accepted DEHu and
custody decisions, the canonical opt-in live test and operator runbook, the
historical live-pull records, and the current guarded route, parser,
persistence, overview, and CLI implementation. The retained independent
review used semantic discovery, exact caller confirmation, focused tests, and
static ownership checks.

## Findings

### operational-rows | medium | five one-time observations were stranded as implementation closure gates

P05.S13 through P05.S16 and P05.S18 described account readiness, an
authenticated pull, inspection of that run, an account-dependent projection,
and packaging its evidence. None delivered missing production capability.
They were retired rather than checked. Optional live acceptance remains owned
by `test_live_notifications_pull_route.py` and the operator deferred-actions
runbook; deterministic parser, legal-state, and Notice behavior remain owned
by their focused tests. The historical S13 record was archived intact.

### guarded-route-ownership | none | no unsafe remote write or duplicate semantic authority was found

The notification query path is a guarded authenticated read. Redirects are
rechecked. The document-detail POST is restricted to already-read content by a
pre-wire guard and is not an acknowledge, mark-read, comparecer, submit, or
presentation route. Parsing, encrypted snapshot persistence, legal-state
computation, overview selection, and CLI command ownership are each
single-homed. No compatibility shim or parallel parser, persistence, or
legal-state implementation was found.

### missing-capture-event | low | the documented snapshot event has no production emitter

`capture_notifications` and `NotificationsService.capture` say the caller
emits `live.notifications.snapshot_captured`, and
`BucketEventKind.LIVE_NOTIFICATIONS_SNAPSHOT_CAPTURED` declares that event,
but no production caller emits it. The CLI pull persists the snapshot and
renders its envelope without appending the event. This is observability and
contract drift, not a remote-route or data-security defect, so it does not
block this review or plan closure.

## Recommendations

- Emit exactly one sanitized snapshot-captured event from the canonical
  application orchestration boundary, or retire the false contract and unused
  enum through the bucket-event owner. Do not create CLI-owned event policy.
- Keep optional authenticated observations in the opt-in test and runbook;
  never recreate permanent live-operation rows in an implementation plan.
