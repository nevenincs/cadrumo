---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:dd33e218edcd1463782d72db2e19d7cefb5a1b83dfd2d39d9bd45c9853c131e2'
step_id: 'S06'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

# after P01 lands, flip the filing_year and period_code canonical-width gate abstentions to 4 and 2, rewriting the abstention comments to state what is now established

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_exports.py`

## Description

- Replace the `filing_year` canonical-width abstention with a real ruling of 4 and
  the `period_code` abstention with a real ruling of 2, in the draft-attribute
  width table the registry build consults for every export field it walks.
- Rewrite both comments to state what is now established rather than what is
  abstained, and drop the forward reference to a restructuring decision that has
  now landed.
- Audit every `draft_attribute` declaration in the registry tree first, through a
  real TOML parse rather than a line-oriented scan, to confirm the flip cannot
  refuse a build: `filing_year` is 4 in all 33 declarations, `period_code` is 2 in
  all 24, and `profile_tax_id` is 9 in all 26.

## Outcome

The abstention that existed only because Modelo 200's page-000 record contradicted
it is gone, replaced by an assertion that would have caught the defect at
authoring time. The abstention was load-bearing while it stood, so removing it
before the declaration was restructured would have refused the registry build;
removing it after is the payoff.

The two remaining abstentions are untouched and keep their own reasons: no
declaration anywhere binds `modelo` or `period`, so no width is observable and any
value chosen would be invented. The `profile_tax_id` ruling a sibling change
installed is untouched.

An initial line-oriented audit of the same question mis-attributed lengths across
adjacent field tables and reported two Modelo 202 offenders plus six
`profile_tax_id` slots at width 2. Re-measuring through a real TOML parse showed
none of them exist. The wrong reading would have blocked this flip.

## Verification

The width-ruling totality gate and both slot-width refusal proofs, which are the
tests that read this table:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py -k "collapsed or draft_attribute_width or parent_tin or nif_draft" -n0 -q
    5 passed, 46 deselected in 6.26s

## Notes
