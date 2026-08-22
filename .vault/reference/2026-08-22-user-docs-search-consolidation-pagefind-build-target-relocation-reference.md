---
tags:
  - '#reference'
  - '#user-docs-search-consolidation'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:3f2ac44d3bfadf26d3ca21d6b5d895bed68bd803e8acea65549f130f9df3ba5f'
related:
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

# `user-docs-search-consolidation` reference: `Pagefind build target relocation`

This audit traced the Pagefind producer, browser consumer, deployment publisher,
generated-artifact boundary, and ignore rules to close the remaining repository-root
artifact gap.

## Summary

The runtime producer was already relocated in commit `360d4953c2`.
`dev/docs/pagefind_index.py:339` configures Pagefind's context-managed write at
`<html_root>/pagefind/`, avoiding the former second unpathed write into the process
working directory. `dev/docs/tests/test_pagefind_index_write_target.py:55` proves the
working directory remains untouched and the generated index still lands in the given
site.

The canonical local artifact is `docs/_build/html/pagefind/`. Deployment redirects the
same contract to each site root, including `docs/_build/html/<language>/pagefind/`, and
`dev/deploy/docs_static_site.py:849` verifies the uploaded entry file against that built
artifact. `docs/_static/cadrumo-docs.js:318` resolves the browser bundle site-relatively,
so no consumer depends on a repository-root directory.

The remaining drift was operational: a stale repository-root `pagefind/` tree remained
on disk and `.gitignore:90` continued to hide that legacy location. The correct generated
boundary is already ignored by `.gitignore:72` through `docs/_build/`. Removing the stale
tree and the root ignore rule makes any future unpathed write visible while retaining the
intended uncommitted build and deployment artifact.
