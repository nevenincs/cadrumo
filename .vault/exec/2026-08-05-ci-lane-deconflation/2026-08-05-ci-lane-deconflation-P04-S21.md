---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:8f40139ae91f60335e1725b64f3a92e08cf0e6726254c474ec7ea20648bfc347'
step_id: 'S21'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Replace the two bare 303 literals in the relation-source validator with the core enum, they entered in today's operator snapshot rather than becoming newly visible and they red a tree-wide gate for every agent and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_relation_sources.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the two bare 303 literals in the relation-source validator with the core enum, they entered in today's operator snapshot rather than becoming newly visible and they red a tree-wide gate for every agent

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Replace the two bare modelo literals in the relation-source validator with the core enum.

## Outcome

Landed as `267de72822` ("refactor(registry): name the modelo enum in the iva-wallet relation
carve-out"), one file, 3 insertions and 2 deletions.

## Verification

    git log --format=%H --grep="name the modelo enum in the iva-wallet" -1
    git show 267de72822 --numstat
    3       2       src/cadrumo/domain/calculations/registry/_validate_relation_sources.py

The diff is small enough to be the whole evidence and is quoted rather than summarised:

    +from ....core import Modelo
    -            "303",
    +            Modelo.M303.value,
    -            "303",
    +            Modelo.M303.value,

Confirmed zero bare three-digit modelo literals remain in that module.

## Notes

The row records that the literals entered in an operator snapshot rather than becoming newly
visible. That is a provenance claim rather than a code claim and it matters for severity: a
tree-wide gate was red for every agent because of a change made hours earlier, not because a
long-standing violation was newly detected. The fix is three lines; what made it urgent is that
it blocked the fleet rather than one campaign.
