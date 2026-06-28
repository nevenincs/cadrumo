---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-object-backlog-drain-plan]]'
---



# `secure-object-backlog-drain` `P01.S02`

Replaced the registry-source CLI help scaffold placeholders in all
locale catalogues.

- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain/2026-05-22-secure-object-backlog-drain-P01-S02.md`

## Description

Ran the locale scaffold command before editing the catalogues, then
replaced `source_ref_help`, `view_help`, and `sources_app_help` under
the registry-source command surface with localized operator-facing help
text in English, Spanish, Catalan, and Hungarian. During the later gate
re-run, scaffold surfaced the missing
`integrity_attribution_details_help` key, which was also translated
through the locale workflow in all four catalogues.

## Tests

Ran `uv run python -m aeat.locales scaffold` before the catalogue edit
and again when the expanded gate surfaced the details-help key. Ran a
targeted `rg` search for the prior self-referential keys after the edit;
no placeholder values remained.
