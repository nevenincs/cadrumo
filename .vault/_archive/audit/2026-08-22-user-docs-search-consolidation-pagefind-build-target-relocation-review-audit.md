---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:4c666f73becafd469c84031afeed1564fa39f86fc6dbe53f3103e45a1c485356'
related:
  - "[[2026-08-22-user-docs-search-consolidation-pagefind-build-target-relocation-reference]]"
---

# `user-docs-search-consolidation` audit: `Pagefind build target relocation review`

## Scope

Reviewed the Pagefind producer, its write-target regression, the browser and deployment
consumers, generated-artifact ignore boundaries, and the absence of the stale
repository-root output against the approved documentation search architecture.

## Findings

No findings. `dev/docs/pagefind_index.py:339` targets only `<html_root>/pagefind/`;
`dev/docs/tests/test_pagefind_index_write_target.py:56` proves the working directory is
untouched and the site receives the index. `.gitignore:72` covers the canonical
`docs/_build/` artifact while a repository-root `pagefind/` is no longer ignored.
`docs/_static/cadrumo-docs.js:318` and `dev/deploy/docs_static_site.py:870` consume and
verify the same site-relative bundle. The stale repository-root directory is absent.

## Recommendations

No follow-up action is required. Retain the existing write-target regression and keep
repository-root Pagefind output visible to Git so any recurrence is immediately
observable.
