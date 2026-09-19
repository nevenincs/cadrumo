---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:98af4ebf156c3bfaae03b2af9d702b51ff2c3b6ec56040b07634a0528a3c5551'
related: []
---

# `reachability-burndown` audit: `s187 notification summary fetch`

## Scope

Independent closure review of S187 against the reachability plan, its accepted
decision and campaign reference, and the notification-document decision. The
review covered the complete notifications adapter, the migrated auth-state
refusal test, the live application owner and its tests, and the Step Record.
It checked the deleted facade's historical consumers, the coherent deletion of
the summary parser cascade, continued ownership of the summary navigation
warm-up, query-fetch ownership at the application boundary, and preservation of
the read/comparecencia safeguards.

## Findings

No findings.

The pre-change tree referenced `fetch_notifications_summary` only from its own
module documentation, export list, and one auth-state test. No production caller
used it. The deletion removes that facade and its export without changing the
shared `_fetch_and_parse` or `_navigate_and_parse` mechanisms.

`parse_notifications_summary` remains public and retains its fixture-backed
parser coverage. The live `fetch_notifications_query` path still delegates to
the common navigation mechanism, which validates and visits
`_NOTIF_SUMMARY_URL` as its authenticated cookie-jar warm-up before navigating
to the widened query URL. `capture_notifications` continues to call
`fetch_notifications_query`; exact production search found no competing
notifications-list fetch owner.

The migrated auth refusal is equivalent at the boundary under review: both the
deleted summary facade and retained query facade enter `_fetch_and_parse`, where
`storage_state_for_session` rejects a session with no persisted state using the
same translated `SedeNavigationError` before browser construction. The focused
test observes that retained live path and its non-placeholder translation.

The change has no diff in `READ_GUARD_POLICY`,
`assert_notification_content_readable`, or `fetch_notification_document`.
Unread, unknown, and served-but-unread rows therefore remain refused before
AEAT contact, the POST allowance remains restricted to the detail path, and the
binding `leida is True` comparecencia predicate is unchanged.

## Recommendations

Close S187. No follow-up change is required.

Verification: the focused auth-state test, complete adapter notifications suite,
adapter no-write structural suite, and live application notifications suite all
passed: 108 tests in 27.04 seconds.

## Final-scope re-review

The implementation expanded after the initial review when remeasurement exposed
the summary parser as the next test-only outer owner. The final diff deletes
`parse_notifications_summary`, `SummaryTableTipo`, the summary-only parser
branches and helpers, their export, and their identity-specific tests. Exact
search finds none of those names or branches in the production tree. This is a
coherent cascade: the application never consumed a summary snapshot, and the
sole production capture continues through `fetch_notifications_query` and the
query parser.

The summary endpoint itself was not conflated with the deleted parser.
`_NOTIF_SUMMARY_URL` remains part of the read guard and remains the first
navigation in `_navigate_and_parse`. The replacement transport test drives the
query fixture and proves one summary warm-up request followed by one query
request, so retaining the warm-up is behavioral evidence rather than a symbol
census. The final focused auth, adapter, and application suite passed 51 tests
in 18.31 seconds, and focused Ruff validation passed.

### plan-record-drift | medium | The final deletion exceeds the Step action still recorded in the plan

The plan row and Step title still require preserving summary parsing, while the
final implementation deliberately and correctly deletes it. The Step Record's
change list and verification results also describe only the earlier wrapper-only
scope. The implementation is technically sound, but closing it against an
authorization and evidence record that state the opposite outcome would make
the campaign history false.

## Final recommendation

Revise S187 through the plan verbs to authorize the coherent summary-parser
cascade, then update its Step Record with the final changed tests and 51-test
verification. With that governance correction, approve closure; no production
code or test change is requested by this review.

### plan-record-drift | resolved | The plan and Step Record now match the final scope

The plan row now authorizes deletion of the complete test-only notification
summary fetch-and-parse surface, including its summary-only type and parser
branches, while explicitly retaining warm-up navigation and marker validation.
The Step Record carries the same action and scope, names all three changed
implementation/test files, and records the final focused 51-test command and
focused Ruff command. This resolves the governance mismatch without changing
production code.

## Closure verdict

Approve and close S187. The final implementation, tests, plan authorization,
and Step Record agree, and no open review finding remains.
