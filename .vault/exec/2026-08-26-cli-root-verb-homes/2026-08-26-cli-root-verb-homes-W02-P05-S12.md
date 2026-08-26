---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a134ad42bc859ab19ad048bf81224e753875ec627171c8502fad0b40f0d0d172'
step_id: 'S12'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Land the placement gate encoding D1 at narrowest-subject granularity

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/test_root_placement_criterion.py`
- `verify:` `pytest test_root_placement_criterion.py` -> `pass`
