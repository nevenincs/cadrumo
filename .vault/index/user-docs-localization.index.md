---
generated: true
tags:
  - '#index'
  - '#user-docs-localization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d3dff8df0770dde98894cec9ff9592eefe65c680cd9b19a300ae814929a77633'
related:
  - '[[2026-07-18-user-docs-localization-W01-P01-S01]]'
  - '[[2026-07-18-user-docs-localization-W01-P01-S02]]'
  - '[[2026-07-18-user-docs-localization-W01-P01-S03]]'
  - '[[2026-07-18-user-docs-localization-W01-P01-S04]]'
  - '[[2026-07-18-user-docs-localization-W01-P01-S05]]'
  - '[[2026-07-18-user-docs-localization-W01-P02-S06]]'
  - '[[2026-07-18-user-docs-localization-W01-P02-S07]]'
  - '[[2026-07-18-user-docs-localization-W01-P02-S08]]'
  - '[[2026-07-18-user-docs-localization-W01-P02-S09]]'
  - '[[2026-07-18-user-docs-localization-W02-P03-S10]]'
  - '[[2026-07-18-user-docs-localization-W02-P03-S11]]'
  - '[[2026-07-18-user-docs-localization-W02-P03-S12]]'
  - '[[2026-07-18-user-docs-localization-W02-P04-S13]]'
  - '[[2026-07-18-user-docs-localization-W02-P04-S14]]'
  - '[[2026-07-18-user-docs-localization-W02-P04-S15]]'
  - '[[2026-07-18-user-docs-localization-W02-P05-S16]]'
  - '[[2026-07-18-user-docs-localization-W02-P05-S17]]'
  - '[[2026-07-18-user-docs-localization-W02-P05-S18]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S19]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S20]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S21]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S22]]'
  - '[[2026-07-18-user-docs-localization-W03-P06-S23]]'
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-18-user-docs-localization-audit]]'
  - '[[2026-07-18-user-docs-localization-plan]]'
  - '[[2026-07-18-user-docs-localization-research]]'
  - '[[2026-08-01-user-docs-localization-catalogue-drift-audit]]'
---

# `user-docs-localization` feature index

Auto-generated index of all documents tagged with `#user-docs-localization`.

## Documents

### adr

- `2026-07-18-user-docs-localization-adr` - `user-docs-localization` adr: `docs localization via gettext catalogues with an all-languages completeness gate` | (**status:** `accepted`)

### audit

- `2026-07-18-user-docs-localization-audit` - `user-docs-localization` audit: `campaign close honesty review`
- `2026-08-01-user-docs-localization-catalogue-drift-audit` - `user-docs-localization` audit: `translation catalogues were complete against stale source: the masked drift, the tracked backlog, and the gate lesson`

### exec

- `2026-07-18-user-docs-localization-W01-P01-S01` - Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv
- `2026-07-18-user-docs-localization-W01-P01-S02` - Implement user-scope gettext POT extraction as a dev.docs build step writing uncommitted templates with gettext_compact disabled
- `2026-07-18-user-docs-localization-W01-P01-S03` - Wire the Sphinx config to read the build language from an environment switch validated against OutputLanguage, with locale_dirs pointing at the committed catalogue tree and en as default
- `2026-07-18-user-docs-localization-W01-P01-S04` - Scaffold the committed es, ca, and hu per-page catalogue trees via sphinx-intl update from the extracted templates
- `2026-07-18-user-docs-localization-W01-P01-S05` - Add justfile targets for gettext extraction, a single-language user-scope build, and the full language-matrix build
- `2026-07-18-user-docs-localization-W01-P02-S06` - Author the all-languages completeness gate asserting every user-scope page catalogue exists with zero untranslated and zero fuzzy entries per target language, failures enumerated by page, language, and counts
- `2026-07-18-user-docs-localization-W01-P02-S07` - Author the language-set parity gate asserting the docs target languages equal the OutputLanguage members minus the English source exactly
- `2026-07-18-user-docs-localization-W01-P02-S08` - Extend the build gate with per-language nitpicky warnings-as-errors user-scope builds for es, ca, and hu
- `2026-07-18-user-docs-localization-W01-P02-S09` - Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them
- `2026-07-18-user-docs-localization-W02-P03-S10` - Translate the how-to section catalogues to Spanish with full-page domain context
- `2026-07-18-user-docs-localization-W02-P03-S11` - Translate the explanation and reference section catalogues to Spanish
- `2026-07-18-user-docs-localization-W02-P03-S12` - Translate the index, architecture, top-level, and remaining catalogues to Spanish and drive the Spanish completeness gate green
- `2026-07-18-user-docs-localization-W02-P04-S13` - Translate the how-to section catalogues to Catalan with full-page domain context
- `2026-07-18-user-docs-localization-W02-P04-S14` - Translate the explanation and reference section catalogues to Catalan
- `2026-07-18-user-docs-localization-W02-P04-S15` - Translate the index, architecture, top-level, and remaining catalogues to Catalan and drive the Catalan completeness gate green
- `2026-07-18-user-docs-localization-W02-P05-S16` - Translate the how-to section catalogues to Hungarian with full-page domain context
- `2026-07-18-user-docs-localization-W02-P05-S17` - Translate the explanation and reference section catalogues to Hungarian
- `2026-07-18-user-docs-localization-W02-P05-S18` - Translate the index, architecture, top-level, and remaining catalogues to Hungarian and drive the Hungarian completeness gate green
- `2026-07-18-user-docs-localization-W03-P06-S19` - Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration
- `2026-07-18-user-docs-localization-W03-P06-S20` - Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence
- `2026-07-18-user-docs-localization-W03-P06-S21` - Dispatch an independent code review over the campaign commits and action every finding
- `2026-07-18-user-docs-localization-W03-P06-S22` - Run the fresh-context honesty review against the closure summary and persist the audit before declaring the campaign complete
- `2026-07-18-user-docs-localization-W03-P06-S23` - Reconcile post-close user-documentation catalogue drift across Spanish, Catalan, and Hungarian by synchronizing the seven source-divergent pages, translating every incomplete entry across the current thirty-page backlog, and proving the full completeness and fresh-POT equality gates return zero without excluding a page or accepting fuzzy fallback

### plan

- `2026-07-18-user-docs-localization-plan` - `user-docs-localization` plan

### research

- `2026-07-18-user-docs-localization-research` - `user-docs-localization` research: `user documentation localization architecture`
