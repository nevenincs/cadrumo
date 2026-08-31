---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7403fd5e9f1c520272d36ec286975085b60b815e8d429ff4d1100fd61cfaa510'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
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

# `ci-lane-deconflation` audit: `Final review P05 S143 immutable peer proof`

## Scope

Final independent review of immutable source commit `80417ba85f`, the prior S143 HIGH audit, and record-only repair `0ee24c21da`. Reviewed the canonical M200/M390 contract split, direct consumer imports, the repaired execution record, and current HEAD. No source, plan, execution record, or shared-index changes were made by this review.

## Findings

### s143-peer-order-proof | high | The claimed immutable import-order proof does not test order

The new PowerShell command names the correct eight peer imports and runs successfully on the immutable parent and step, but `Compare-Object $parent $step` compares array membership rather than positional sequence. A three-line permutation independently produced `PERMUTED_COMPARE_COUNT=0`, `POSITIONAL_MATCHES=1`, and passed the same guard. Consequently a reordered peer hunk would still print `IMMUTABLE_PEER_IMPORT_ORDER_UNCHANGED=true`; the literal result is unsound for its stated order-preservation claim. The underlying source relocation remains sound: the old producer module exposes none of the 23 moved contracts, direct M200 consumers use the defining sibling, the recorded semantic lane is 12 passing, and no threshold or baseline change was found.

## Recommendations

For `s143-peer-order-proof`, repair only the execution record with a positional comparison, for example joining both filtered arrays with a newline and comparing those joined strings using case-sensitive equality, while retaining the full literal parent and step output and exit status. Re-run and record the exact result before approval.

