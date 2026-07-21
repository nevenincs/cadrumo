---
tags:
  - '#reference'
  - '#docs-static-deployment'
date: '2026-07-11'
modified: '2026-07-11'
related:
  - "[[2026-07-10-docs-static-deployment-adr]]"
---
# `docs-static-deployment` reference: `Pagefind delivery`

## Summary

- `dev/docs/build.py` indexes every full strict HTML build.
- `docs/pagefind.yml` is absent from the built HTML root.
- `dev/docs/pagefind_index.py` writes the Pagefind index twice.
- Unconfigured Pagefind indexes generated API and viewcode pages.
- Generated tax-record injection blocks public publication.
- `sphinx_sitemap` omits normal documentation pages.
- `dev/deploy/docs_static_site.py` hides build output until child exit.

## Required repair

- Read `pagefind.yml` into Pagefind configuration.
- Write the Pagefind index once.
- Exclude `api` and `_modules` from Pagefind input.
- Keep API and source pages public.
- Use page-only search for public deployment.
- Generate the public sitemap from human docs and CLI pages.
- Fail deploy when Pagefind fails.
- Stream build output during publish.
