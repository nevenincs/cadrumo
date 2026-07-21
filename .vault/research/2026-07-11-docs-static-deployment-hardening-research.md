---
tags:
  - '#research'
  - '#docs-static-deployment-hardening'
date: '2026-07-11'
modified: '2026-07-11'
related:
  - "[[2026-07-10-docs-static-deployment-adr]]"
---
# `docs-static-deployment-hardening` research: `Cadrumo delivery safeguards`

Research the Cadrumo deploy controls after closeout review.

## Findings

- Add post-invalidation `200`, `308`, `404`, and `403` checks; `dev/deploy/docs_static_site.py:357-367`.
- Refuse `CI` and `GITHUB_ACTIONS`; `dev/deploy/docs_static_site.py:370-394`, `justfile:675-719`.
- Defer immutable releases; `dev/deploy/docs_static_site.py:295-310`, `infra/docs-static-site.yaml:47-48`, `infra/docs-static-site.yaml:121-130`.
- Keep local human-gated deployment; `.vault/adr/2026-07-10-docs-static-deployment-adr.md:30-44`.
