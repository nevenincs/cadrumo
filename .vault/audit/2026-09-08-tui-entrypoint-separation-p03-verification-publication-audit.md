---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:648871016407f6aa2b013b1ee8a1a07296793047cb9ee461e69fbb6ad3b81774'
related: []
---

# `tui-entrypoint-separation` audit: `p03 verification publication`

## Scope

## Findings

### stale-published-tui-route-docs | medium | Published documentation still names the retired global request and deleted destination module

The generated locale catalogues at `docs/locales/{ca,es,hu}/LC_MESSAGES/download.po` retain the
message "Add `--tui` to work in a full-screen interface instead:". The API document
`docs/api/cadrumo.entrypoints.tui.rst` still includes the deleted
`cadrumo.entrypoints.tui.destination_session` module, and its dedicated API page remains. These
published artefacts contradict the new `aeat app tui` seam and leave documentation referencing a
module P02 removed. Regenerate or update the owning documentation outputs and remove the obsolete
API page before closing P03.

## Recommendations
