---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2ae50f444285acf85a58facb5224764e2d35368b8c677961646d816ea1ef882b'
step_id: 'S04'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Localize Cadrumo-owned annual-manual coverage labels and status messages

## Scope

- `src/cadrumo/locales`

## Changes
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `uv run pytest -n 0 src/cadrumo/application/registry/tests/test_corpus.py::test_manuals_list_report_localizes_the_unpublished_acquisition_condition -q --disable-warnings --maxfail=1` -> `pass`
