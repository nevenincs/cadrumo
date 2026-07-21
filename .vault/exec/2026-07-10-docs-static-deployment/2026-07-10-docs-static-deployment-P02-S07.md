---
tags:
  - '#exec'
  - '#docs-static-deployment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S07'
related:
  - "[[2026-07-10-docs-static-deployment-plan]]"
---
# `docs-static-deployment` `P02.S07` execution

## Result

- Read Pagefind selectors from `docs/pagefind.yml`.
- Exclude generated API and source pages from search.
- Keep generated API and source pages public.
- Keep full tax-record injection for local builds.
- Use page-only search for public deployment.
- Write the Pagefind index once.
- Generate canonical human-docs and CLI sitemap entries.
- Stream deploy build output.
- Require the sitemap root and Pagefind data.

## Verification

- Pass Pagefind integration tests.
- Pass deployment tests.
- Pass sitemap tests.
- Pass Ruff and syntax checks.
- Pass independent review.
