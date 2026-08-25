---
tags:
  - '#audit'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bbc9866380134fa077d8667af0af8b4b5f0b0921a689647f9a924dc368c0815c'
related: []
---

# `dehu-notification-legal-effect` audit: `P04.S09 verification review`

## Scope

Formal P04.S09 review of the DEHu legal-effect plan, ADR, reference, Step
records, canonical core, overview, and CLI surfaces, their direct tests, and
the captured P04 logs. The serial legal-catalogue rerun is green (158 passed),
as are the locale scaffold and vault commands. The original parallel
legal-catalogue failure reports concurrent registry fingerprinting and is
superseded by the required sequential rerun. The remaining core,
application-overview, and entrypoint-CLI red signatures concern storage,
configuration, hashing, repository-wide literal scans, explain/agenda,
ledger-payload contracts, module-size budgets, and profile recovery; none is
on this feature's canonical surfaces or current diffs.

## Findings

### message-only-event-invariant | medium | The typed calendar event admits a service state on filing rows

The plan and `OverviewCalendarEvent` documentation limit
`notificacion_estado_servicio` to `message` rows projected from notification
snapshots, but the model has no cross-field validation. The CLI payload test
constructs a `filing` event with a non-null service state and asserts that the
invalid combination round-trips. That value can therefore cross the JSON
boundary and makes the filing event actionable through the deemed-service limb,
allowing the dedicated legal notice to make an art. 43.2 claim about a
non-notification reference. The current notification projection emits only
`message` rows, but that producer-side discipline does not protect this public
DTO from another producer or future caller.

### message-only-event-invariant-disposition | medium | Resolved at the canonical event-model boundary

`OverviewCalendarEvent` now rejects a non-null
`notificacion_estado_servicio` when `event_type` is not `message`. The CLI
payload regression now projects the state through a real message event and
proves a filing event carrying `RECHAZO_TACITO` fails validation before it can
reach the actionability or Notice path. The direct owner-surface regression
run passed 15 selected tests.

## Recommendations

- For `message-only-event-invariant`, add a strict model-level invariant that
  rejects a non-null `notificacion_estado_servicio` unless `event_type` is
  `message`. Make the payload roundtrip use a real message notification event,
  add the refusal case at the DTO boundary, and rerun the P04 target suites.
