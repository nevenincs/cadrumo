---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3505e3898518851dbb5301ee97da5e17dbd089d2bbb66215f4c55ba31cab069f'
step_id: 'S10'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Verify companion-package inclusion and the manual operator surface across the supported horizon

## Scope

- `packaging/cadrumo_data_manuals`

## Changes

- `verify:` `uv run python -c "... ZipFile(...).namelist() ..."` -> `pass`
- `verify:` `uv run pytest dev/packaging/tests/test_cadrumo_data_distribution.py` -> `fail`

## Notes

The real source-tree wheel contains the 2022 and 2023 Sociedades PDFs. The
tracked-artifact parity gate correctly refuses to pass until those newly
acquired corpus inputs are staged or committed; no index mutation was
authorised.
