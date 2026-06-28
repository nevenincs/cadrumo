---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S01'
related:
  - '[[2026-05-22-secure-object-backlog-drain-plan]]'
---



# `secure-object-backlog-drain` `P01.S01`

Audited the locale catalogues for the registry-source scaffold
self-references identified during secure-object closeout.

- Modified: none
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain/2026-05-22-secure-object-backlog-drain-P01-S01.md`

## Description

The locale CLI audit passed for all four catalogues. A targeted search
confirmed that `cli.registry.sources.source_ref_help`,
`cli.registry.sources.view_help`, and `cli.registry.sources_app_help`
remain self-referential in `src/aeat/locales/en.yml`,
`src/aeat/locales/es.yml`, `src/aeat/locales/ca.yml`, and
`src/aeat/locales/hu.yml`.

## Tests

Ran `uv run python -m aeat.locales audit`; all catalogues reported ok.
Ran a targeted `rg` search for the registry-source placeholder keys and
confirmed the exact replacement scope for `P01.S02`.
