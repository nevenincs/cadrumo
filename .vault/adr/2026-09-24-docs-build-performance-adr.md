---
tags:
  - '#adr'
  - '#docs-build-performance'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:31e892788d95eb793cdc7327c30c2e430220562f2a6e580446d195ee40170bb4'
related:
  - "[[2026-09-24-docs-build-performance-research]]"
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-09-23-website-repository-boundary-docs-cloudflare-delivery-adr]]"
  - '[[2026-07-20-ci-speed-redesign-adr]]'
---

# `docs-build-performance` adr: `the documentation build does each piece of work once` | (**status:** `accepted`)

## Problem Statement

A documentation publish takes hours: the first root alone took 214 minutes in CI,
and a publish builds five. `2026-09-24-docs-build-performance-research` shows the
time is not the content but repeated work: the navigation is recomputed and
re-embedded in full for every page, the English full-scope site is built twice, the
sequence gate runs two or three times and rebuilds identical sandboxes per
sequence, and nothing is kept between builds. The accepted CI speed decision caps a
single step at ten minutes. The operator directed that the architecture be fixed
rather than the symptoms patched.

## Considerations

- Every page must remain usable without JavaScript
  (`2026-07-13-docs-cli-sequences-adr`, rejected client-only rendering).
- The navigation layout is not otherwise constrained by any accepted decision.
- The localization decision describes one English full-scope root and three
  user-scope roots (`2026-07-18-user-docs-localization-adr`).
- The goldens gate must fail the build on drift and stay mandatory before upload
  (`2026-07-13-docs-cli-sequences-adr` D6,
  `2026-09-23-website-repository-boundary-docs-cloudflare-delivery-adr`).

## Considered options

- Client-rendered navigation from one shared file: smallest pages, but pages
  without JavaScript lose navigation. Rejected as the primary form.
- Keep Furo's full tree and cache its rendering per directory: removes the CPU cost
  but keeps 72% of every page as repeated bytes. Rejected.
- Collapsed server-rendered navigation built once per build (chosen, D1).
- Larger CI runners or more workers alone: parallelism multiplies the same wasted
  work. Rejected as a substitute; adopted on top (D4).

## Constraints

- The navigation must match the collapsed tree Sphinx itself produces, so Furo's
  decoration, styling and accessibility behaviour are unchanged.
- The verdict cache may never turn a failing gate green: its key covers everything
  the verdict depends on, and a cache hit prints its origin.

## Implementation

- D1: A docs extension builds the navigation tree once per build from the Sphinx
  environment's toctree map and renders, per page, the collapsed tree (ancestors,
  their siblings, top-level sections, the page's own children) in the HTML shape
  Sphinx's `collapse=True` produces. It is supplied to Furo through the page
  context's `toctree` callable. Sphinx's own collapsed output is the test oracle.
- D2: One English full-scope root. The apex carries only the language entry, the
  404 page and crawler files. The Worker redirects an apex path that is not a
  language root to the same path under `/en/`, so existing deep links keep working.
- D3: The sequence gate runs once per publish. Each gate worker provisions one
  template sandbox and clones it per sequence, and the validated authority snapshot
  is built once per process. A verdict cache keyed by the content of the CLI source,
  the registry authority, contracts, goldens, seeds, fixtures and mask set lets an
  unchanged tree skip re-execution; this amends D6 of
  `2026-07-13-docs-cli-sequences-adr` only by allowing a proven identical verdict to
  be reused.
- D4: The language roots build concurrently, and the Sphinx doctree environment of
  each root persists in a size-bounded, runner-local cache so unchanged pages are
  not re-read.

## Rationale

Each decision removes repeated work at its source. D1 alone removes 89% of the
write phase and most page bytes; D2 halves the full-scope builds; D3 turns the gate
from minutes of setup into the cost of the commands it proves; D4 converts the
remaining cost from cold and serial to incremental and parallel. The design keeps
every page complete without JavaScript and keeps the gate's failure semantics.

## Consequences

- Readers see the collapsed navigation Sphinx's standard themes use: the current
  branch expanded, other sections one click away.
- Published pages shrink by roughly two thirds; uploads shrink accordingly.
- The apex no longer serves its own copy of the English site; deep links are
  redirected to `/en/`.
- A stale or corrupted verdict cache can only cost a re-run, never a pass, because
  a miss re-executes and the key is content-derived.
