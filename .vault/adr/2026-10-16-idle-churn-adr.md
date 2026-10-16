---
tags:
  - '#adr'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:b31dc7d051555df3fa76951568c92076b5b8a8658c78a17b4fd4704ef592db2d'
related:
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - '[[2026-10-16-idle-churn-audit]]'
---

# `idle-churn` adr: `No idle polling: pushed observation across desktop, service, runtime and worker` | (**status:** `accepted`)

## Problem Statement

With the desktop open and idle, Cadrumo uses about 1.2 cores. The runtime alone uses 56% of a core, and the desktop spawns a CLI process every two seconds. Every one of these costs is a fixed-interval loop that re-reads state which has not changed. The loops run in the desktop, the agent service, the session hold, the runtime, the profile worker and the shared transport. Each re-derives authority facts from disk and the OS on every turn. The measurements and locators are in `2026-10-16-idle-churn-audit`. The operator ruled on 2026-10-16 that every recurring check must be driven by a real signal: Tauri channels on the desktop side, and event-driven waits instead of Python wait-with-timeout process loops.

## Considerations

- `2026-10-04-application-sign-in-adr` already commits the runtime to pushed session events on bounded per-connection queues, where overflow closes the connection, and says pushed events end the polling window. It also lets polling remain as a fallback, and leaves event framing and field names as hypotheses.
- `2026-10-04-desktop-shell-adr` keeps the shell process free of any runtime connection, session, receipt or credential. Its sign-in observation is the `sign-in-status` read it polls. Long-lived product children that hold a connection already exist under `2026-10-12-desktop-agent-host-adr` (`cadrumo-runtime session hold`).
- `2026-10-12-desktop-agent-host-adr` has the service poll its connection for the issued lease. It also requires generation and deadline observation that does not refresh idle time.
- A status read spawned from the desktop costs about 1.5 s of CPU in the child, plus the runtime's evaluation (`2026-10-16-idle-churn-audit`).
- Desktop sign-in is supported only on Windows (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:349`).
- A running peer executes the image mapped when its process started. Windows refuses writes to a mapped image, so re-hashing the file on disk proves nothing more about a peer whose kernel incarnation is unchanged.

## Considered options

- **Keep polling, but slower and shared.** This cuts the churn several-fold. It still wakes every process for nothing, and it leaves staleness proportional to the interval. Rejected under the operator's ruling.
- **A runtime connection inside the shell.** This gives direct events. It reverses the shell's central ruling, and the Rust host would then need the transport and admission code. Rejected.
- **Pushed invalidation cues plus one re-read, with the shell observing through a long-lived product child.** The authority checks on every read are unchanged, no process wakes while nothing changes, and the shell keeps its no-connection rule. Chosen.

## Constraints

- Cues carry no authority, no private fact and no deadline. A client that receives a cue re-reads through the existing request, and that request re-checks authority as before. A missing cue never grants anything. A lost connection is observed as a disconnect, and a reconnect re-reads.
- Cues travel on the existing per-connection queues. A cue that is already pending for a connection is not queued again, so a burst of changes cannot overflow a queue and close it.
- The shell process still holds no runtime connection, session, receipt or credential. It starts only fixed, digest-verified product children.
- Recurring checks are driven by events, by one-shot timers set at a known deadline, or by OS change notifications. A fixed-interval loop is allowed only where the platform offers no notification source, and only as that platform's observation source. Bounded retries while a runtime is unavailable are reconnection, not idle polling.
- A service request after admission still proves the kernel incarnation of the admitted peer (pid, creation time, retained handle, channel peer) before it is served. The image is verified at admission, and again whenever the incarnation differs.
- This amends `2026-10-04-application-sign-in-adr` ("Polling remains as a fallback"), `2026-10-04-desktop-shell-adr` (sign-in learned "otherwise from the `sign-in-status` read it already polls"), and `2026-10-12-desktop-agent-host-adr` ("service polls its same connection for the issued lease"). Each of those records carries an amendment note pointing here.

## Implementation

We will remove every idle polling loop named in `2026-10-16-idle-churn-audit` and replace each with an event source.

- **Cues.** Connection events gain `sign_in_changed` for sign-in watchers, `service_lease_changed` for a service connection, and `attendance_changed` for a profile's person connections. The language cue is published when an operation completes for the profile, not by re-reading the hint file on every transport turn.
- **Sign-in watch.** A `sign_in_status` request may ask to watch. The runtime then publishes `sign_in_changed` to that connection on human login, sign-out, retirement, held sign-in disconnect, host retirement, and any change in the observed OS login or lock state.
- **Desktop.** The shell starts one `cadrumo-runtime session watch` child per window. It writes one JSON line for each change in presence, profile label, private profile id or runtime availability, and re-reads on a cue, on a pointer-directory change notification, and at the earliest status deadline. The sign-in view, the language host and the agent host all consume that one observation over Tauri channels and an in-process watch channel. Profile id resolution no longer spawns a child. Language and attendance refresh on event lines from the shared session hold, and the window receives attendance changes on a channel.
- **Agent service.** It blocks on one queue fed by its connection's events, its stdin lifetime and a disconnect. It claims on start and after a cue, and keeps the generations it observed until a cue or its own write invalidates them.
- **Runtime.** It verifies a service image once per connection and rechecks the kernel incarnation on every later request. Lifecycle observation wakes on deadlines, explicit wakes and, on Windows, WTS session notifications. The accept wait also wakes on those, instead of turning every 0.2 s.
- **Worker.** Custody expiry waits for the earliest lease deadline or a custody change.
- **Transport.** Idle connection loops block on the channel and a wake handle instead of peeking every 1-50 ms.

Hypotheses that may change within the constraints: the cue names and fields; the `session watch` line shape; whether an OS lock-state change is detected by notification or by a re-observation at the next wake on platforms without WTS; the exact wait primitive on each platform.

## Rationale

The fact the runtime authority already re-checks on every read is what makes invalidation cues safe: correctness never depended on the polls, only on the checks they triggered. Driving those reads by change instead of by clock removes nearly all of the idle cost without moving an authority boundary. The watch child keeps the shell's rule intact for the same reason the session hold does. The shell starts and stops a product command, and the command holds the connection.

## Consequences

- Idle CPU falls to the cost of blocked threads. Process churn stops: the desktop starts no children while nothing changes.
- New protocol: three cues, a watch flag, and the `session watch` child with its line shape. Both sides ship together under the pinned expected version.
- Staleness now depends on every mutation path publishing its cue. A mutation path that misses one shows stale state until the next cue or deadline. Each cue site needs a test that drives the mutation and observes the cue.
- On platforms without an OS session notification source, the runtime keeps a periodic lifecycle observation. Reconsider when a notification source exists there.

Accepted 2026-10-16 under the operator's ruling in this session: "Everything is using proper tauri signals for recurring checks. Ensure you migrate everything that is ineffective python side blocker waits as process loop."
