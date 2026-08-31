---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c508d38d3c9cf5fb6b7d8d4f34a6b08d37c066917803a91b8c4d591e9a639efa'
step_id: 'S33'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep the three non-gate-covered docs locale catalogues

## Scope

- `docs/locales/`

## Changes

- `M` `docs/locales/es/LC_MESSAGES/` (catalogue refresh)
- `M` `docs/locales/ca/LC_MESSAGES/` (catalogue refresh)
- `M` `docs/locales/hu/LC_MESSAGES/` (catalogue refresh)
- `verify:` `python -m dev.docs.i18n` -> `pass`

## Notes

The catalogue refresh surfaced a gap in S32: that sweep replaced full command
forms but not the shorthand the prose uses (`reconcile file`, `doclink`,
`sync calc export`). Six how-to pages carried those and were corrected before
the catalogues were regenerated.
