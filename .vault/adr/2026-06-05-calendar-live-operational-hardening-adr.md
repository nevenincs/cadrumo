---
tags:
  - '#adr'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
  - '[[2026-06-04-calendar-live-filing-integration-live-verification-audit]]'
---

# `calendar-live-operational-hardening` adr: `live calendar hardening remains read-only and locally projected` | (**status:** `accepted`)

## Problem Statement

Follow-up live calendar work needs to repair operational gaps discovered during
read-only verification without broadening the calendar into a remote-read or
submission surface. Filed declarations, expedientes, and notifications improve
calendar evidence only after they have been captured and persisted through the
live read boundary.

## Considerations

The accepted calendar live filing integration decision already places live reads
under explicit live commands and keeps overview projection local-only. The
operational hardening plan continues that design by adding missing facades,
classifying unsupported live boundaries, and verifying read-only behavior.

## Constraints

No overview calendar command may open a live session or submit anything to AEAT.

Unsupported registry/live combinations must be reported explicitly rather than
hidden as empty calendar evidence.

CLI additions remain thin transports over application services.

## Implementation

Live operational hardening adds or repairs live command facades for persisted
filed declarations, expedientes, and notification state. Calendar projection
continues to consume only the local persisted results of those commands.

Unsupported filed-capture combinations return structured unsupported-boundary
diagnostics instead of silent omission.

## Rationale

Keeping the hardening wave under the same read-only/local-projection contract
avoids accidental semantic expansion while still making calendar evidence
usable for operators.

## Consequences

Operators get clearer live-read commands and diagnostics. Calendar output
becomes better populated after explicit live capture, but remains safe to run
offline.

## Codification candidates

- **Rule slug:** `live-calendar-hardening-stays-read-only`.
  **Rule:** Calendar live hardening may add read and projection surfaces, but
  must not add submission behavior or implicit live reads to overview commands.
