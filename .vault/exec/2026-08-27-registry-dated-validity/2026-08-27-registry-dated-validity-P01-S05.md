---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:409c4bfb5208747f73d1bf323f9913686fdf9932fbe48355bfeddf4b3dcc1b11'
step_id: 'S05'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Add the anti-mirror gate refusing a citation whose reference or url names a filing year while its window reaches outside that year, keyed on the citation's own two fields so no allowlist is possible

## Scope

- `src/cadrumo/domain/categories/tests/`

## Changes

- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `A` `src/cadrumo/domain/categories/tests/test_citation_edition_window.py`
- `verify:` `pytest src/cadrumo/domain/categories/tests/test_citation_edition_window.py` -> `pass`
