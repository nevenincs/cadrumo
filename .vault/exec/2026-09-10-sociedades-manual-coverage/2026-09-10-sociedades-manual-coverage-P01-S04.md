---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:86e69473fafc4caa0525aef3db5ba21d8c6007217b1abefa041a1b7569ddf1e4'
step_id: 'S04'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

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
