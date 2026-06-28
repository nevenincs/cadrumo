---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S25'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P04.S25 complete Hungarian Modelo 100 2024 help slice

Scope: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/locales/hu`.

## Description

- Identify that Hungarian labels were complete through `1856`, while Hungarian help still had placeholders for `1838` through `1856`.
- Update Hungarian help leaves `1838` through `1856` with `python -m aeat.locales modelo set`.
- Verify the current Hungarian M100 2024 coverage through the modelo locale CLI.
- Run a structured placeholder scan over present M100 2024 keys from `0750` through `1856`.

## Outcome

The Hungarian slice is complete for present keys through `1856`. CLI coverage now reports `etiquetas=1797/2068 ayuda=1797/2068`, and the focused placeholder scan found zero placeholder labels or help values in the verified `0750` through `1856` boundary.

## Notes

This step does not close the full M100 2024 Hungarian campaign. The next untranslated placeholders start at `1857`, with later residual placeholders through `2148` and `DPFNAC_D`.
