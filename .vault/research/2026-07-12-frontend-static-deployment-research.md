---
tags:
  - '#research'
  - '#frontend-static-deployment'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-10-docs-static-deployment-adr]]"
---
# `frontend-static-deployment` research: `Cadrumo frontend delivery`

Research the existing Cadrumo frontend publisher.

## Findings

- Reuse `cadrumo-docs`; one CloudFront alias can own `cadrumo.neve.md`.
- Publish Vite `dist` to bucket root; preserve `docs/*`.
- Keep S3 private behind current OAC; `infra/docs-static-site.yaml:94-155`.
- Keep root `200`, root missing `404`, docs `200`, and direct S3 `403` checks.
- Keep local human-gated publishing and CI refusal.
- Treat current frontend WIP as the explicit publish candidate; `frontend/` is dirty.
- Add publisher tests before publishing the newer landing build.
- Live root assets differ from `frontend/dist`; current root is older.

## Sources

- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/src/App.tsx:18-22`
- `dev/deploy/frontend_static_site.py:51-148`
- `infra/docs-static-site.yaml:94-155`
- `aws:cloudformation:cadrumo-docs`
