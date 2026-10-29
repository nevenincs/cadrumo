---
tags:
  - '#adr'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:248ac524a7f2ccfacb391f356a64801c7c5fa88456f962f797be2a4a502e723e'
related:
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-29-desktop-aeat-sync-adr]]"
  - '[[2026-10-29-desktop-aeat-sync-reference]]'
---
# `desktop-aeat-sync` adr: `Amend desktop shell: AEAT sync run family and last-capture time` | (**status:** `proposed`)

## Problem Statement

`2026-10-04-desktop-shell-adr` lets the window start AEAT reads only through the census band and the Sede view, and its 2026-10-23 amendment says the census band shows no last-synchronized time because no product read reports one. The AEAT sync page (`2026-10-29-desktop-aeat-sync-adr`) adds a host-run family of AEAT read captures and a product read that reports the last capture time. This record holds the proposed amendment until it is applied.

## Considerations

- `2026-10-23-desktop-modelo-workspace-adr` added a writing family to the shell with a closed, manifest-checked id list; the same pattern applies.
- The 2026-10-27 amendment keeps domain data and logic out of the window.

## Considered options

- **Amend the accepted record.** Kept: the shell record owns what the window may start.
- **Leave the census sentence.** Rejected: it would become untrue once `live.sync.status` exists; ADRs state current truth.

## Constraints

Proposed amendment text, to be appended to the accepted record once authorized:

> **Amendment: AEAT sync page.** The `aeat-sync` page brings AEAT data into the profile through the host's `aeat_sync_*` commands, which submit only the closed list of read captures in `2026-10-29-desktop-aeat-sync-adr`. The run is held by the host for the signed-in profile, survives page navigation and is discarded on sign-out, profile change and window close. The window receives closed states, outcomes and served wording only. Nothing is submitted to AEAT.
>
> **Census entries.** The one Censo flow (the `profile_censo_*` commands and the profile page's band) is reachable from a global command palette action on every page, the profile page, the Modelo page and the AEAT sync page's census area. Each entry opens the same flow; none duplicates it.

And, in the 2026-10-23 amendment's Censo item, the sentence "The band shows no last-synchronized time, because no product read reports one." is replaced by: "The band shows the census's last capture time served by `live.sync.status`."

## Implementation

Applied by editing the accepted record's body once the user authorizes it, then retiring this proposal.

## Rationale

The shell record stays the single place that lists what the window may start.

## Consequences

The census band may show its last capture time once the read exists.
