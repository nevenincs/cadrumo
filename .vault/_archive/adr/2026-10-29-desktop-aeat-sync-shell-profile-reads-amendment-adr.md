---
tags:
  - '#adr'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:98691fcdb68bbe445c433f8fd8a8d9547be7eb2ef51a00091b639c86d7820e95'
related:
  - "[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]"
  - "[[2026-10-29-desktop-aeat-sync-adr]]"
  - '[[2026-10-29-desktop-aeat-sync-reference]]'
---

# `desktop-aeat-sync` adr: `Amend shell profile reads: AEAT sync views` | (**status:** `proposed`)

## Problem Statement

`2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr` admits two named views and states that sync counts are out of scope because no product read gives them. The AEAT sync page (`2026-10-29-desktop-aeat-sync-adr`) needs an area status view and a notification rows view. This record holds the proposed amendment until it is applied to the accepted record.

## Considerations

- Each further view is added by amending the accepted record.
- `live.sync.status` is a new registered read with no effect, so it fits the record's read-only rule once it exists.
- The current notifications summary withholds rows because they carry names and tax numbers.

## Considered options

- **Amend the accepted record with two views.** Kept: it is the record's own extension path.
- **Serve the views outside this record.** Rejected: it would bypass the closed view list.

## Constraints

Proposed amendment text, to be appended to the accepted record once authorized:

> **Amendment: AEAT sync views.** Two views are added. The AEAT sync status view submits `live.sync.status` for the signed-in profile and passes on, per area, the served state, the last capture instant, the last attempt outcome where given and the served counts. The notification rows view submits `live.notifications.latest` and `live.notifications.show` and passes on each row's subject wording, dates, category and read state; the window receives no snapshot or row identifier, only an opaque per-view position. Sync counts are no longer out of scope: `live.sync.status` gives them. Every other ruling of this record stands.

## Implementation

Applied by editing the accepted record's body once the user authorizes it, then retiring this proposal.

## Rationale

Keeps the closed list of views authoritative and states current truth about sync counts.

## Consequences

The sentence "Sync counts are out of scope: no product read gives them" is replaced in the accepted record.
