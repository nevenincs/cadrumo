---
tags:
  - '#adr'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:374addc956fbb87ae8a56834b6623e36375099dcc34ea4deedaf56a87741f60a'
related:
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-10-29-desktop-aeat-sync-adr]]"
  - '[[2026-10-29-desktop-aeat-sync-reference]]'
---

# `desktop-aeat-sync` adr: `Amend sync control surface: desktop AEAT areas, stop and progress` | (**status:** `proposed`)

## Problem Statement

`2026-08-08-sync-control-surface-adr` rules dry run, scope, last-sync provenance and cancellation for the filed sweep and the Sheets export. It says cancellation is interruption-safety rather than a cancel control, that progress has no channel, and (Consequences) that none of it is implemented, although the filed sweep now writes sync-run records (`src/cadrumo/application/live/filed_data_capture.py:705`). The AEAT sync page (`2026-10-29-desktop-aeat-sync-adr`) adds a stop control between items, item-level progress and a served last-capture time for every AEAT area. This record holds the proposed amendment until it is applied.

## Considerations

- Live captures declare cancellation `unsupported`; a stop between items keeps every operation's interruption-safety intact.
- The runtime observation already carries an event cursor; filed captures emit typed progress events.

## Considered options

- **Amend the accepted record.** Kept: it owns sync control semantics.
- **Add cooperative cancel to the live captures.** Deferred: a backend change to every capture, not needed for a stop between items.

## Constraints

Proposed amendment text, to be appended to the accepted record once authorized:

> **Amendment: the desktop AEAT sync page.** The desktop's stop control stops a run between items: the in-flight capture settles and nothing further starts. It interrupts no operation, so the interruption-safety ruling stands. Progress for the desktop is item-level, refined by the operation's own observation events where it emits them; the CLI envelope is unchanged. Last-sync provenance for every AEAT area is served by `live.sync.status`: the filed sweep's typed sync-run record where one exists, otherwise the latest stored capture's own instant. Dry run on the filed sweep remains the only AEAT dry run; it reads AEAT and saves nothing.

And the Consequences statement that none of this is implemented is replaced by the current state: the filed sweep writes the typed sync-run record.

## Implementation

Applied by editing the accepted record's body once the user authorizes it, then retiring this proposal.

## Rationale

Extends the ruling to the desktop without weakening interruption-safety, and restores current truth.

## Consequences

A cooperative cancel in the live captures would need a further amendment.
