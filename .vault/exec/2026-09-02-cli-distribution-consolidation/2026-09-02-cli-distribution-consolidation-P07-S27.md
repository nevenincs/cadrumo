---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:473220e0104327a22b7e6419da16b5ea79ac7ed7258a7be0304de25d482581a1'
step_id: 'S27'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Rewrite the install page around the primary registry

## Scope

- `docs/download.md`

## Changes

M docs/download.md
M dev/docs/download_matrix.py

## Notes

The page names the primary registry and defers to the generated channel table for the
commands themselves, rather than repeating them in prose. Duplicating them was the
defect: install commands have one authoritative home, the channel inventory, and a hand
written copy both forks that fact and makes an acquisition claim the page cannot back.

The generated table is safe to carry the commands because documentation is delivered
downstream of a release, and a release cannot publish without the evidence rows its
channels owe. A reader therefore only ever sees commands for a version that shipped.

The page's beta framing, its checkout instructions and its links to a release page that
does not exist are gone with it.
