---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S16'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-sphinx-ux with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-04-docs-sphinx-ux-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The inspect desktop and mobile rendered UX and ## Scope

- `docs/_build/html` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
