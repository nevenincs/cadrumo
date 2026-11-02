---
tags:
  - '#exec'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:347779a30ff429cd4e0354aef73918c499a9d1f19079968ce1b4103741401219'
related:
  - "[[2026-11-02-cadrumo-windowmanager-plan]]"
---

# `cadrumo-windowmanager` ledger

## Changes

- `S01` `A` `native/desktop/frontend/src/shell/docking.ts`
- `S01` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S01` `A` `native/desktop/frontend/tests/live/docking.unit.ts`
- `S01` `verify:` `node --test tests/live/docking.unit.ts` -> `pass`
- `S01` `verify:` `tsc --noEmit` -> `pass`
- `S01` `verify:` `eslint .` -> `pass`
- `S01` `by:` `CADRUMO-WINDOWMANAGER`

## Notes

- `S01` Semantic discovery unavailable: client 0.6.0 / service 0.6.4 mismatch; owning ADR listing and static source discovery used.
