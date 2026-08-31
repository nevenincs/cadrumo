---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:646cf8997fad92e46e93c5ae194536d0282298055885ec84257c0b685f71bb0d'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S182]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `p05 s182 execution self review`

## Scope

Independent self-review of the P05.S182 execution record against source provenance `4ced237398edb70bd54a0eef6550fda705dc0d70`, its four-path manifest and immutable physical/raw line comparison, supplied focused receipts, the mixed integration receipt, size-budget-policy boundary, and isolated vault-artifact scope.

## Findings

### p05-s182-execution-self-review | low | Integration receipt is non-green but unrelated to the split

The exact receipt is `1 passed, 2 failed, 4 deselected in 293.23s`. Both failures concern shared `corpus_catalogue` `applies_across` behavior rather than the `authority.py` split, so the execution record accurately retains them as a limitation and makes no green integration claim.

### p05-s182-execution-self-review | high | Count labeling corrected

An earlier correction inaccurately called nonblank PowerShell line counts committed raw counts. The corrected record now carries only the immutable physical/raw comparison for source commit `4ced237398edb70bd54a0eef6550fda705dc0d70`: 1365 parent `authority.py` lines, 1142 committed `authority.py` lines, and a new 253-line sibling. It also completes the commit manifest with both direct-consumer import repoints.

### p05-s182-execution-self-review | low | No baseline or threshold mutation

Neither the source commit nor the corrected execution record changes a size-budget baseline or threshold.

## Recommendations

Keep the two shared `corpus_catalogue` failures separately owned and rerun the integration selection once that shared surface is stable; do not use this record as a green integration receipt. Keep the peer filing-relocation portions of the two mixed `dev/registry` paths outside the S182 source-commit attribution.
