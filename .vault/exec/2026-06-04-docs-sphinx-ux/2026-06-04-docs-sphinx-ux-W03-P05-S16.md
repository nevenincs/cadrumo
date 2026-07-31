---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:ebc0c057fde2916185979f7291fa40a90f1d705f7f87b08acd863297252c76a0'
step_id: 'S16'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# inspect desktop and mobile rendered UX

## Scope

- `docs/_build/html`

## Description

- Build the full documentation site with the canonical builder and serve it
  locally.
- Inspect the rendered experience in a real browser session (Playwright) at
  desktop 1440x900 and mobile 375x812 viewports: the landing page (light
  theme), the route grid, the safety admonition, the curated Python API
  overview, the CLI reference (dark theme), and the header/sidebar
  navigation.
- Capture viewport screenshots per surface as inspection evidence.
- Re-verify the rendered output after fixing the finding below.

## Outcome

- Desktop light theme: branded header, pre-alpha broadcast with the AEAT
  deadline warning, above-the-fold Important disclaimer, sectioned sidebar
  (profile / calendar / ledger / filings), serif display headings — all
  render correctly with no overflow.
- Mobile: hamburger navigation, gracefully truncating broadcast banner, the
  route grid stacks to a single column, no horizontal scroll.
- Dark theme (CLI reference): strong contrast, legible code chips, active
  nav highlighted, command-family cards and global-flags sections render
  correctly.
- Curated API overview renders with working per-package links and correct
  breadcrumbs.
- FINDING (fixed during inspection): the custom header's primary-nav API
  entry still pointed at the generated root (`api/cadrumo`) instead of the
  curated overview after the S11 retarget — a second nav surface defined in
  `docs/conf.py` `html_context`. Fixed in commit `61f17e7cae`; the site was
  rebuilt and the rendered header and sidebar both now target `api/index`.

## Notes

- The visual inspection was performed by the coordinator session directly
  (real rendered pages in a real browser engine), satisfying the plan's
  "machine checks are necessary but insufficient" requirement with an
  actual visual pass. The three explicit human-approval gates (S18, S21,
  S25) remain open for the operator and are served by a consolidated
  review packet prepared from this same build.
