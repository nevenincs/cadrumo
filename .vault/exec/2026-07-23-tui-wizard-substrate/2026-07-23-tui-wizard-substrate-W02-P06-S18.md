---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S18'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Implement the render-time copy assembler resolving i18n keys and typed schema and locale references, refusing literal strings and unresolvable references loudly

## Scope

- `src/cadrumo/application/flows/_copy.py`

## Description

- Resolve every page copy slot at render time against i18n keys and typed schema and locale references, refusing literal strings and unresolvable references loudly.
- Support multiple resolvers per copy kind (first non-None wins) so modelo and profile schema-field namespaces coexist, and add the legal-zone copy slot.
- Landed in `26615cd4e6`, extended by the multi-resolver support `f065545fd7` and the legal-zone slot `9803d782ec`.

## Outcome

Copy is assembled by reference from schema and locale sources only, never literals and never the legal corpus; an unresolvable reference raises rather than rendering blank.

## Notes

None.
