---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6cdc12873b5dfaef32e0286aac8858bc18672519148e36e3c71c7de66308eed2'
step_id: 'S06'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m200-export-envelope-tag with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The after P01 lands, flip the filing_year and period_code canonical-width gate abstentions to 4 and 2, rewriting the abstention comments to state what is now established and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_exports.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

The width-ruling totality gate and both slot-width refusal proofs, which are the
tests that read this table:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py -k "collapsed or draft_attribute_width or parent_tin or nif_draft" -n0 -q
    5 passed, 46 deselected in 6.26s

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
