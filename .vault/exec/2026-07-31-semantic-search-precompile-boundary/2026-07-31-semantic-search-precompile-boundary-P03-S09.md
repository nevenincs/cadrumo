---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:130d4f666edc7efc035b7b54320de39af71cffedb610b9e84310e162432c4763'
step_id: 'S09'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

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
