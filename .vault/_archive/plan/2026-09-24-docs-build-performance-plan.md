---
tags:
  - '#plan'
  - '#docs-build-performance'
date: '2026-09-24'
tier: L1
related:
  - '[[2026-09-24-docs-build-performance-adr]]'
modified: '2026-09-24'
body_schema: body-v2
body_hash: 'sha256:1649b7f096a468e72284a3f951240c67257516844d5054b4bf7ec86a79b08237'
---

# `docs-build-performance` plan

## Description

Approved 2026-09-24. The operator directed that the documentation build's
architecture be fixed rather than its symptoms patched ("tackle the deep
architectural issues"); `2026-09-24-docs-build-performance-adr` records the
decisions this plan executes, grounded in
`2026-09-24-docs-build-performance-research`.

## Steps

- [x] `S01` - Build the collapsed navigation once per build and supply it to Furo, proven equal to Sphinx's collapsed toctree; `dev/docs/navigation.py`.
- [x] `S02` - Build one English full-scope root and redirect apex deep links to /en/ in the Worker; `dev/deploy/docs_static_site.py`.
- [x] `S03` - Run the sequence gate once per publish, clone a template sandbox per sequence, cache the authority snapshot per process, and reuse content-keyed verdicts; `dev/docs/sequences/runner.py`.
- [ ] `S04` - Build the language roots concurrently with a runner-local doctree cache; `dev/deploy/docs_static_site.py`.
- [ ] `S05` - Publish through CI and record the build time against the ten-minute step budget; `.github/workflows/release.yml`.

## Parallelization

Steps run in order: each is measured before the next, and S02-S04 change the
same publisher.

## Verification

- The navigation matches Sphinx's collapsed toctree for every page of a fixture
  site, and a built page is at least 60% smaller than before.
- A publish builds one full-scope English root, and an apex deep link redirects to
  the same page under `/en/`.
- An unchanged tree reuses the gate verdict; any change to a key input re-runs it.
- The CI publish completes well within the job budget, with the time recorded.
