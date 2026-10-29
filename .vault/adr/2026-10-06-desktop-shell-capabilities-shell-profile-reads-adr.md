---
tags:
  - '#adr'
  - '#desktop-shell-capabilities'
date: '2026-10-06'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:cdb6e2c2cc39f046ff5c9cf5038f0aa014600c398b9807cede066dfeb6f205d3'
related:
  - "[[2026-10-06-desktop-shell-capabilities-research]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-06-04-calendar-live-filing-integration-adr]]"
  - "[[2026-06-05-calendar-filing-semantics-adr]]"
---

# `desktop-shell-capabilities` adr: `The desktop shell may show named read-only views of the signed-in profile` | (**status:** `accepted`)

Accepted 2026-10-22 on the owner's request that day to make the calendar and Messages buttons work in the desktop window after sign-in.

## Problem Statement

The user asked on 2026-10-06 for the desktop window to show a count of messages from the tax agency and a calendar of filing obligations. `2026-10-04-desktop-shell-adr` rules that the shell holds no runtime connection and no runtime authority, with named exceptions. Neither view can be built without one more exception, so the ruling is widened deliberately for these views only.

## Considerations

- The product already answers both questions as typed, read-only, registered operations with no effect: `overview.calendar`, and `live.notifications.latest` with `live.notifications.show` (`2026-10-06-desktop-shell-capabilities-research`).
- The host already holds the signed-in person's registered-operation relay and reads the profile page through it (`native/desktop/src-tauri/src/shell/user_profile.rs`, `user-profile.view`). The same relay carries these reads under the same exact-profile session, with no new channel and no runtime connection in the shell.
- Local projections distinguish never captured, stale, unknown and empty. A count that hides those differences would misstate the profile.
- Reading a projection must never cause a request to the tax agency (`2026-06-04-calendar-live-filing-integration-adr`).
- Taxpayer data shown in the window is private data: it must not be written to the window's storage, its logs or its diagnostics.

## Considered options

- **Keep the ruling; link to the TUI only.** The rail offers buttons that open the TUI. No count, no calendar in the window.
- **Named reads over the held person's relay (chosen).** The host gains one command per view; each submits fixed registered reads for the signed-in profile and returns a typed result.
- **A general operation bridge.** The frontend names any operation to run. One host change serves every future view, and turns the window into an unreviewed operator surface.
- **A runtime connection for the shell.** The shell becomes a runtime client of its own. This reverses the shell decision's central ruling for the sake of two views.

## Constraints

- This adds one exception to `2026-10-04-desktop-shell-adr`: named read-only views of the signed-in profile. That record's other rulings stand: the shell holds no session, receipt, credential or runtime connection, and shows no runtime control.
- The host exposes a closed list of view commands. Each submits fixed registered reads chosen by the host; the frontend supplies at most typed, validated parameters: a date range of at most about a year and an output language. There is no command that takes an operation.
- Every operation so used is a registered read with no effect. It never starts a capture, a sync, a sign-in or any request to the tax agency.
- A view is read only while the account is signed in, and the answer is rejected when the held account changed while it was read. The host keeps nothing it reads. The shell holds a view in memory only and discards it on sign-out, on a change of profile and when the window closes: never in the window's storage, a log line, a diagnostic snapshot or an error message.
- The views keep the product's own distinctions. Never captured, stale, unknown and empty are shown as such; a count is shown only where the product gives one, and an unknown is never drawn as zero. A profile without a declared taxpayer model is said, in the product's own sentence, rather than drawn as nothing due.
- A failed or refused read is shown as unavailable with its code, never retried automatically. A read is bounded in time as the profile read is.
- The views are the notifications summary, the filing calendar, the AEAT sync status view and the notification rows view. Each further view is added to the list by amending this record. Sync counts are served by `live.sync.status` through the AEAT sync status view. The profile's Drive folder is out of scope: `2026-10-04-google-app-identity-adr` reserves it.

## Implementation

The host's profile module serves two commands beside the profile read, `profile_views_calendar` and `profile_views_notifications` (`native/desktop/src-tauri/src/shell/user_profile/views.rs`), serialized with the profile read on the same relay.

- The calendar submits `overview.calendar` for the signed-in profile with the requested range and output language, checks that the answer names that profile and range, and returns the shell's `FilingCalendar` type (`native/desktop/frontend/src/shell/views.ts`): entries with the day each filing window opens, observed events, warnings, generation time and coverage. Closed product states are parsed as closed values; an unknown value refuses the read. A warning carries the product's sentence in the read's language, from the calendar warning snapshot's `text` (`src/cadrumo/application/overview/read_calendar_item_projection.py`); its `message` stays the locale key for clients that render keys themselves.
- The notifications summary submits `live.notifications.latest` and, where a capture exists, `live.notifications.show` for that capture. The host counts the rows and passes on only the capture time, the row count and the number of rows the agency had not marked as read; a row whose read mark was not captured is not counted as unread. The rows themselves, which carry names and tax numbers, never reach the window. Never captured is its own answer.
- The `Host` port's optional `views` (`native/desktop/frontend/src/shell/host.ts`) is offered by the desktop host (`native/desktop/frontend/src/shell/tauriHost.ts`). A host without them offers none, and the shell then shows no button, action or page for a view; the scenario host answers them from data, so each state of each view can be designed without a host. The rail's Messages button shows the unread count and opens the TUI; the calendar is a page of the shell.

## Rationale

The reads already exist, are already admitted by the runtime for the signed-in person, and already have a carrier in the host. Naming each view in the host keeps the window from becoming a second operator surface, which separates this from a general bridge, and leaves the shell without a connection of its own, which separates it from the fourth option.

## Consequences

- The window answers two questions the person otherwise opens the TUI for.
- Each new view costs a host command, contract types, a scenario and a review; that cost is the control.
- Private data enters the webview's memory. The constraints on storage and logging are things to test, in the browser and in the packaged window.
- A view is as fresh as the last local capture; the window says so rather than imply the agency's current state.
- Reconsider if a view needs to change anything, if the number of views makes per-view commands a burden, or if the runtime gains a read-only client role the shell could hold safely.

### Amendment 2026-10-29: AEAT sync views

Accepted by the owner on 2026-10-29 with `2026-10-29-desktop-aeat-sync-adr`. Two views are added. The AEAT sync status view submits `live.sync.status` for the signed-in profile and passes on, per area, the served state, the last capture instant, the last attempt outcome where given and the served counts. The notification rows view submits `live.notifications.latest` and `live.notifications.show` and passes on each row's subject wording, dates, category and read state; the window receives no snapshot or row identifier, only an opaque per-view position. Every other ruling of this record stands.
