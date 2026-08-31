---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:14d9b84a8e4afa5151ccbf0cca657a9724a5787480ba05c813ef0c98a69831e2'
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

# `ci-lane-deconflation` audit: `Review P05 S212 IVA classification predicates`

## Scope

Independent review of immutable P05.S212 commit `1c41ebec3e`, its plan and execution record, IVA classification source and legal predicate rationale, import topology, direct public consumers, focused IVA/downstream behavior, and policy/baseline scope. This review made no source, plan, execution-record, or shared-index change.

## Findings

No HIGH or CRITICAL findings. The private sibling retains the moved R01 through R30 predicate family and territorial sets with their legal rationale, while `classification` retains the public enums/models, Article 69 helper, closed 21-row decision table, and canonical `classify_iva` resolver. Initialization is safe: the public types needed by predicates are defined before the private sibling import, and the only `_classification_rules` import is the canonical module's private dependency; all production and test consumers continue to import public contracts directly from `classification`. Ruff and format pass, public resolver import reports the canonical module and 21 rules, focused IVA tests pass 138 of 138, downstream tests pass 41 of 41, and source measures 1014 and 421 lines against the unchanged 1250 cap. No policy or baseline path changed.

## Recommendations

Approve P05.S212. Preserve the current one-way import shape: public classification owns types and table; the private sibling owns predicates only.
