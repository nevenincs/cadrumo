---
tags:
  - '#plan'
  - '#docs-static-deployment-hardening'
date: '2026-07-12'
modified: '2026-07-12'
tier: L1
related:
  - '[[2026-07-12-docs-static-deployment-hardening-adr]]'
  - '[[2026-07-11-docs-static-deployment-hardening-research]]'
---
# `docs-static-deployment-hardening` plan

Harden Cadrumo documentation delivery.

## Description

Enforce public verification and human-only publishing.

## Steps

- [x] `S01` - Enforce endpoint checks and CI refusal; `dev/deploy/docs_static_site.py`.
- [x] `S02` - Verify local delivery safeguards; `src/aeat/tests/test_docs_static_site.py`.
- [x] `S03` - Accept no-change stack deployments; `docs/runbooks/RB-006-cadrumo-docs-delivery.md`.
- [x] `S04` - Verify the live delivery contract; `src/aeat/tests/test_docs_static_site_live.py`.
## Parallelization

Implement `S01` before `S02`.

## Verification

Require focused tests and live endpoint checks.
