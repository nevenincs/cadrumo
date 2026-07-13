---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S15'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Regroup docs/how-to/index.md and the landing-page route grid on the filing-year axes (entry points, profile, calendar, ledger, filings, residuals) per the ratified disposition table and ## Scope

- `docs/how-to/index.md docs/index.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regroup docs/how-to/index.md and the landing-page route grid on the filing-year axes (entry points, profile, calendar, ledger, filings, residuals) per the ratified disposition table

## Scope

- `docs/how-to/index.md docs/index.md`

## Description

- Rewrite `docs/how-to/index.md` on the ratified filing-year axes: Get
  started (onboarding, quickstart), Your profile (profile-setup,
  authenticate, censo, choose-modelo, protect-data-access), Your calendar
  (filing-calendar, notifications, filing-readiness), Your ledger (import,
  classify, LLM, evidence, invoices, corrections, prorrata), Your filings
  (filing-spine, the six modelo pages, calculation inputs, Sheets review,
  verification, file-at-aeat, reconcile), Tools and help (agent,
  troubleshooting, runbooks). Add the "This page covers the ..." opening;
  reorder the toctree to match the groups; add grid cards for the three new
  modelo pages.
- Update the landing `docs/index.md` route grid: the tutorial card becomes
  "Follow a Whole Filing Year" naming both lifecycle tutorials, and the
  filing-workflow card becomes "Prepare Your Filings", naming the six
  per-modelo recipes.

## Outcome

The how-to surface reads in the order a taxpayer lives the year, and the
landing page routes to the two lifecycle tutorials and the per-modelo
recipes explicitly.

## Notes

`prorrata` moved from the "How does this work?" group into Your ledger per
the disposition table.
