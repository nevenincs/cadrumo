---
tags:
  - '#plan'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-08-23'
body_hash: 'sha256:14d1a6433677422523123d3d4ad140685d5e321ad82afad4b752fee836f62daf'
tier: L3
related:
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-18-user-docs-localization-research]]'
---

# `user-docs-localization` plan

## Description

## Steps

## Wave `W01` - localization infrastructure and gates

Land the gettext extraction, catalogue tree, per-language build wiring, and the all-languages completeness gates

### Phase `W01.P01` - gettext tooling and catalogue scaffold

Dependencies, POT extraction, conf.py language wiring, committed es/ca/hu catalogue tree, justfile targets

- [x] `W01.P01.S01` - Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv; `pyproject.toml, uv.lock`.
- [x] `W01.P01.S02` - Implement user-scope gettext POT extraction as a dev.docs build step writing uncommitted templates with gettext_compact disabled; `dev/docs/build.py, dev/docs/i18n.py`.
- [x] `W01.P01.S03` - Wire the Sphinx config to read the build language from an environment switch validated against OutputLanguage, with locale_dirs pointing at the committed catalogue tree and en as default; `docs/conf.py`.
- [x] `W01.P01.S04` - Scaffold the committed es, ca, and hu per-page catalogue trees via sphinx-intl update from the extracted templates; `docs/locales`.
- [x] `W01.P01.S05` - Add justfile targets for gettext extraction, a single-language user-scope build, and the full language-matrix build; `justfile`.

### Phase `W01.P02` - holistic completeness gates

All-languages-present gate, OutputLanguage parity gate, per-language -W build matrix, docs-check integration

- [x] `W01.P02.S06` - Author the all-languages completeness gate asserting every user-scope page catalogue exists with zero untranslated and zero fuzzy entries per target language, failures enumerated by page, language, and counts; `dev/docs/tests/test_docs_localization.py`.
- [x] `W01.P02.S07` - Author the language-set parity gate asserting the docs target languages equal the OutputLanguage members minus the English source exactly; `dev/docs/tests/test_docs_localization.py`.
- [x] `W01.P02.S08` - Extend the build gate with per-language nitpicky warnings-as-errors user-scope builds for es, ca, and hu; `dev/docs/tests/test_docs_build.py`.
- [x] `W01.P02.S09` - Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them; `justfile, dev/docs/tests`.

## Wave `W02` - translation of the user-scope corpus

Translate every user-scope page catalogue into Spanish, Catalan, and Hungarian until the completeness gate is green per language

### Phase `W02.P03` - Spanish translation

Translate all user-scope page catalogues to es with domain context, gate green

- [x] `W02.P03.S10` - Translate the how-to section catalogues to Spanish with full-page domain context; `docs/locales/es`.
- [x] `W02.P03.S11` - Translate the explanation and reference section catalogues to Spanish; `docs/locales/es`.
- [x] `W02.P03.S12` - Translate the index, architecture, top-level, and remaining catalogues to Spanish and drive the Spanish completeness gate green; `docs/locales/es`.

### Phase `W02.P04` - Catalan translation

Translate all user-scope page catalogues to ca with domain context, gate green

- [x] `W02.P04.S13` - Translate the how-to section catalogues to Catalan with full-page domain context; `docs/locales/ca`.
- [x] `W02.P04.S14` - Translate the explanation and reference section catalogues to Catalan; `docs/locales/ca`.
- [x] `W02.P04.S15` - Translate the index, architecture, top-level, and remaining catalogues to Catalan and drive the Catalan completeness gate green; `docs/locales/ca`.

### Phase `W02.P05` - Hungarian translation

Translate all user-scope page catalogues to hu with domain context, gate green

- [x] `W02.P05.S16` - Translate the how-to section catalogues to Hungarian with full-page domain context; `docs/locales/hu`.
- [x] `W02.P05.S17` - Translate the explanation and reference section catalogues to Hungarian; `docs/locales/hu`.
- [x] `W02.P05.S18` - Translate the index, architecture, top-level, and remaining catalogues to Hungarian and drive the Hungarian completeness gate green; `docs/locales/hu`.

## Wave `W03` - deployment, verification, and close

Per-language deploy roots and switcher, full matrix verification, code review, honesty review, campaign close

### Phase `W03.P06` - deploy matrix and campaign close

Per-language site roots and switcher, full verification, reviews, close

- [x] `W03.P06.S19` - Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration; `dev/deploy/docs_static_site.py, docs/_templates`.
- [x] `W03.P06.S20` - Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence; `dev/docs/tests, docs/locales`.
- [x] `W03.P06.S21` - Dispatch an independent code review over the campaign commits and action every finding; `.vault/audit`.
- [x] `W03.P06.S22` - Run the fresh-context honesty review against the closure summary and persist the audit before declaring the campaign complete; `.vault/audit`.
- [ ] `W03.P06.S23` - Reconcile post-close user-documentation catalogue drift across Spanish, Catalan, and Hungarian by synchronizing the seven source-divergent pages, translating every incomplete entry across the current thirty-page backlog, and proving the full completeness and fresh-POT equality gates return zero without excluding a page or accepting fuzzy fallback; `docs/locales/{es,ca,hu}/LC_MESSAGES; dev/docs/tests/test_docs_localization.py; dev/docs/tests/test_docs_catalogue_drift.py`.

## Parallelization

## Verification
