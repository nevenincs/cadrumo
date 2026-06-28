---
tags:
  - '#adr'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
---

# `calendar-live-filing-integration` adr: `calendar events over local live-read snapshots` | (**status:** `accepted`)

## Problem Statement

The application has a profile-derived filing calendar, a live AEAT filed-declarations backend, an expedientes snapshot service, and a DEHU notifications service. These are useful separately, but the operator needs one calendar that shows both legal obligation dates and actual AEAT events already captured into the profile bucket.

The missing backend gap is bulk remote capture. Listing can iterate all registry modelos, but justificante/declaration capture is limited to one modelo/year command invocation.

## Considerations

- Overview calendar must remain local-only and must not trigger live AEAT reads.
- Live AEAT reads belong under `aeat app live`, specifically `aeat app live filed` for filed declarations.
- The deadline engine is the authority for verified filing windows and holiday shifts.
- Persisted expedientes and notifications snapshots are already bucket-scoped and encrypted.
- "All modelos" can only honestly mean all modelos known to the local registry and exposed by the live AEAT form. Bulk capture must report failures per modelo/year/declaration rather than imply universal AEAT support.

## Constraints

- No live submission path may be introduced.
- No overview command may call `require_live_read`, open a browser, or contact AEAT.
- Calendar event projection must be additive so existing `entries` clients keep working.
- CLI commands stay thin and delegate orchestration to application services.
- Tests must exercise real application/domain behavior without mocks, stubs, monkeypatches, skips, or tautological mirrored logic.

## Implementation

Add typed `OverviewCalendarEvent` records to the overview application layer. Keep deadline obligations in `entries`; add `events` for observed AEAT facts such as filed declarations and received messages. Provide pure helpers that project `PersistedExpedientesSnapshot` and `PersistedNotificationsSnapshot` records into events inside a requested calendar range.

Wire `aeat app overview calendar` to load local persisted expedientes and notifications snapshots for the active bucket, project them into calendar events, and include them in the typed output. The command remains local-only because it only reads local secure objects.

Add an application-level `capture_filed_data_bulk` service and an `aeat app live filed capture-all` command. The service performs one authenticated live-read session, iterates registry modelos and years, attempts to capture every returned declaration artefact, persists successful observations, and returns a typed report with explicit failure rows.

## Rationale

Separating obligations from observed events preserves the existing legal-deadline contract while giving the operator the actual calendar they asked for. Persisted live-read snapshots are the correct source for overview integration because they are already bucket-scoped, local, and read-only.

Bulk filed capture belongs beside the existing filed live commands. It improves operator ergonomics without weakening the live-read gate or adding any AEAT write/submission capability.

## Consequences

- Calendar JSON consumers receive a new `events` array and can continue using existing `entries`.
- Operators can see obligation due dates, filed AEAT declarations, and AEAT messages in one calendar response after running the relevant live capture commands.
- Bulk capture may produce partial success. That is intentional and safer than hiding unsupported modelos or extraction drift.
- Future work can add bucket-event emission for `live.filed.capture_created` if not already wired in the affected path.

## Codification candidates

- **Rule slug:** `overview-calendar-local-live-projection`.
  **Rule:** Overview calendar may project persisted live-read state, but must never initiate a remote AEAT read.
