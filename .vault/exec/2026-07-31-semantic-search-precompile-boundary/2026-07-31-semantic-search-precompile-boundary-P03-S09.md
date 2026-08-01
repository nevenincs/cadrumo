---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:aeed7788699c38da96f89028e6d873c9e9a84734206af92c5441a86d245f0329'
step_id: 'S09'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Retire CorpusSearchDependencyError together with its error-registry row, and remove its locale keys through the locales CLI leaving scaffold check clean and ## Scope

- `src/cadrumo/core/errors/registry/_application_part1.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire CorpusSearchDependencyError together with its error-registry row, and remove its locale keys through the locales CLI leaving scaffold check clean

## Scope

- `src/cadrumo/core/errors/registry/_application_part1.py`

## Description

- Retire `CorpusSearchDependencyError` from `corpus_search/_errors.py`, since the retrieval surface needs no optional package and can never refuse for want of one.
- Remove its error-registry row from `core/errors/registry/_application_part1.py`.
- Remove its four locale keys through the locales CLI (`ca`, `en`, `es`, `hu`), leaving `scaffold --check` clean.
- Update the errors-registration test so its raise-site suggestion-override assertion targets a refusal that still exists, instead of one that no longer does.

## Outcome

Landed as part of commit `13935ef3a2` "build(search): drop the search extra and its dependency refusal" (same commit as S08 — the plan's Parallelization section allows S08-S10 to run in parallel after P02, but the executing agent landed S08 and S09 together). Confirmed by `git show --stat 13935ef3a2`: `corpus_search/_errors.py` changed 19 lines, `core/errors/registry/_application_part1.py` dropped 11 lines (the registry row), `tests/test_errors_registration.py` changed 19 lines, and `locales/ca.yml`, `en.yml`, `es.yml`, `hu.yml` each dropped 2 lines (the four locale keys).

## Notes

None.
