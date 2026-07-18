---
generated: true
tags:
  - '#index'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
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
  - '[[2026-07-18-user-docs-localization-W03-P06-S19]]'
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-18-user-docs-localization-plan]]'
  - '[[2026-07-18-user-docs-localization-research]]'
---

# `user-docs-localization` feature index

Auto-generated index of all documents tagged with `#user-docs-localization`.

## Documents

### adr

- `2026-07-18-user-docs-localization-adr` - `user-docs-localization` adr: `docs localization via gettext catalogues with an all-languages completeness gate` | (**status:** `accepted`)

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
- `2026-07-18-user-docs-localization-W03-P06-S19` - Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration

### plan

- `2026-07-18-user-docs-localization-plan` - `user-docs-localization` plan

### research

- `2026-07-18-user-docs-localization-research` - `user-docs-localization` research: `user documentation localization architecture`
