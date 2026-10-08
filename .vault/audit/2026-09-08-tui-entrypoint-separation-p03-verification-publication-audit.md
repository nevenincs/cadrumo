---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:7c12c707f6e9c683dde83db3be434a7888bc4b500b75c4e7e4ba461b9684ce1e'
related: []
---

# `tui-entrypoint-separation` audit: `p03 verification publication`

## Scope

Check generated locale and published API documentation for stale references to the retired global TUI request after the opaque app launcher was introduced.

## Findings

### stale-published-tui-route-docs | medium | Published documentation still names the retired global request and deleted destination module

The generated locale catalogues at `docs/locales/{ca,es,hu}/LC_MESSAGES/download.po` retain the
message "Add `--tui` to work in a full-screen interface instead:". The API document
`docs/api/cadrumo.entrypoints.tui.rst` still includes the deleted
`the retired destination-session module` module, and its dedicated API page remains. These
published artefacts contradict the new `aeat app tui` seam and leave documentation referencing a
module P02 removed. Regenerate or update the owning documentation outputs and remove the obsolete
API page before closing P03.

## Recommendations

Regenerate or update the locale and API outputs from the current aeat app tui seam, and remove the obsolete destination-session API page and module entry before closing P03.
