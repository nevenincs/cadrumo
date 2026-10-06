---
tags:
  - '#adr'
  - '#desktop-shell-capabilities'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:272c1a01209a74e64b32cf6cf0b0122bec8c8d152bb96af6167acf301418a944'
related:
  - "[[2026-10-06-desktop-shell-capabilities-research]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-06-04-calendar-live-filing-integration-adr]]"
  - "[[2026-06-05-calendar-filing-semantics-adr]]"
---

# `desktop-shell-capabilities` adr: `The desktop shell may show named read-only views of the signed-in profile` | (**status:** `proposed`)

## Problem Statement

The user asked on 2026-10-06 for the desktop window to show a count of messages from the tax agency and a calendar of filing obligations. `2026-10-04-desktop-shell-adr` rules that the shell holds no runtime connection and no runtime authority, with three exceptions that all concern sign-in. Neither view can be built inside that ruling, so the ruling has to be widened deliberately or the views refused.

## Considerations

- The product already answers both questions as typed, read-only, registered operations with no effect, surfaced as `app live notifications latest` and `app overview calendar` (`2026-10-06-desktop-shell-capabilities-research`).
- Those reads need an exact-profile client under the signed-in session. Only a command-line process holds one; the shell must not acquire one of its own.
- The host already runs the command line for sign-in as a short child process with fixed arguments and bounded output. The same shape carries a read without a new channel.
- Local projections distinguish never captured, stale, unknown and empty. A count that hides those differences would misstate the profile.
- Reading a projection must never cause a request to the tax agency (`2026-06-04-calendar-live-filing-integration-adr`).
- Taxpayer data shown in the window is private data: it must not be written to the window's storage, its logs or its diagnostics.

## Considered options

- **Keep the ruling; link to the TUI only.** The rail offers buttons that open the TUI. No count, no calendar in the window. Nothing new to secure, and nothing of what was asked for beyond a shortcut.
- **Named reads through the host's command-line child (chosen).** The host gains one command per view; each runs one fixed, read-only product command under the signed-in session and returns its typed result.
- **A general command bridge.** The frontend names any command to run. One host change serves every future view, and turns the window into an unreviewed operator surface.
- **A runtime connection for the shell.** The shell becomes a runtime client of its own. This reverses the shell decision's central ruling for the sake of two views.

## Constraints

- This widens the exceptions of `2026-10-04-desktop-shell-adr` by a fourth: named read-only views of the signed-in profile. That record's other rulings stand: the shell holds no session, receipt, credential or runtime connection, and shows no runtime control.
- The host exposes a closed list of view commands. Each maps to exactly one product command with fixed arguments chosen by the host; the frontend supplies at most typed, validated parameters such as a date range. There is no command that takes a command.
- Every product command so used is a registered read with no effect. It never starts a capture, a sync, a sign-in or any request to the tax agency.
- A view is read only while the account is signed in, and is discarded on sign-out, on a change of profile and when the window closes. It is held in memory only: never in the window's storage, never in a log line, a diagnostic snapshot or an error message.
- The views keep the product's own distinctions. Never captured, stale, unknown and empty are shown as such; a count is shown only where the product gives a count, and an unknown is never drawn as zero.
- Output and time are bounded as they are for sign-in, and a failed or refused read is shown as unavailable with its code, never retried automatically.
- The first two views are the notifications summary and the filing calendar. Each further view is added to the list by amending this record. Sync counts are out of scope: no product read gives them. The profile's Drive folder is out of scope: `2026-10-04-google-app-identity-adr` reserves it.

## Implementation

We will let the desktop host run named, read-only product commands for the signed-in profile and return their typed results to the shell, starting with the notifications summary and the filing calendar.

The host adds one command per view beside the sign-in commands and reuses their process handling. The contract's types for each view are published in the frontend's contract file, and the `Host` port gains one method per view; the browser host reports them unavailable and the scenario host answers them from data, so each state of each view can be designed without a host. The rail's messages button shows the unread count the summary gives and opens the TUI; the calendar is a page of the shell that lists obligations with their deadlines and the product's own state for each.

Hypotheses, not commitments: that the notifications summary is cheap enough to read on window focus; that an unread count can be derived from the latest snapshot's rows without a dedicated field; that the calendar's payload fits the bounded output for a twelve-month range.

## Rationale

The reads already exist, are already admitted by the runtime for the signed-in person, and already have a carrier in the host. Naming each view in the host keeps the window from becoming a second operator surface, which is what separates this from a general bridge, and leaves the shell without a connection of its own, which is what separates it from the fourth option.

## Consequences

- The window can answer two questions the person otherwise opens the TUI for.
- Each new view costs a host command, contract types, a scenario and a review; that cost is the control.
- Private data enters the webview's memory. The constraints on storage and logging become things to test, in the browser and in the packaged window.
- A view is as fresh as the last local capture; the window must say so rather than imply the agency's current state.
- Reconsider if a view needs to change anything, if the number of views makes per-view commands a burden, or if the runtime gains a read-only client role the shell could hold safely.
