---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:77a95f040c193bb715125a477740deead26aff9c2db2f6fe8ae3f02a18224054'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `w03 p06 s16 off host projection review`

## Scope

Reviewed the S16 removal of the off-host acquisition projection against the catalog-backed manifest and registry identity boundaries, including the immediate synchronizer dependency scheduled for S17.

## Findings

### s16-off-host-loader | high | The isolated deletion leaves the synchronizer unable to run

`check()` and two focused support tests still call `_load_off_host_sources()`, which reads the deleted projection and now raises `FileNotFoundError`. The catalog and exact-alignment tests establish that the seven rows are duplicate declarations, but they do not make the S16 commit independently runnable. S17 must remove the loader, its schema and routing, and S18 must remove or replace the coupled tests before the record-design quality gate can pass.

## Recommendations

- Complete and verify S17 and S18 as the immediate follow-up before treating the off-host lane retirement as integrated.
