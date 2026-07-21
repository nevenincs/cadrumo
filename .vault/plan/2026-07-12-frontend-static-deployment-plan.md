---
tags:
  - '#plan'
  - '#frontend-static-deployment'
date: '2026-07-12'
modified: '2026-07-12'
tier: L1
related:
  - '[[2026-07-12-frontend-static-deployment-adr]]'
  - '[[2026-07-12-frontend-static-deployment-research]]'
---
# `frontend-static-deployment` plan

Publish Cadrumo frontend without changing documentation.

## Description

Build, test, and locally publish the landing page through the shared private origin.

## Steps

- [x] `S01` - Protect docs during root synchronisation; `dev/deploy/frontend_static_site.py`.
- [x] `S02` - Add default-discovered offline publisher tests; `src/aeat/tests/test_frontend_static_site.py`.
- [x] `S03` - Add opt-in live delivery-contract tests; `src/aeat/tests/test_frontend_static_site_live.py`.
- [x] `S04` - Publish the approved build with literal confirmation; `dev/deploy/frontend_static_site.py`.
- [x] `S05` - Isolate deployment build output; `frontend/vite.config.ts`.
- [x] `S06` - Refuse CI before publisher setup; `dev/deploy/frontend_static_site.py`.
- [x] `S07` - Restrict deployment build output selection; `frontend/vite.config.ts`.
- [x] `S08` - Expose root synchronisation dry-run; `dev/deploy/frontend_static_site.py`.
## Parallelization

Finish `S01` before `S02` and `S03`.

Finish `S02` and `S03` before `S04`.

## Verification

Require local tests, live contract, and protected docs.
