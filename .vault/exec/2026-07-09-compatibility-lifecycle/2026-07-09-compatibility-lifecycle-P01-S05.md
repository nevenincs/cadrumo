---
tags:
  - '#exec'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S05'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace compatibility-lifecycle with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-09-compatibility-lifecycle-plan placeholders are machine-filled by
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
     The Ship the empty cross-version fixture-corpus harness (directory + vacuous coverage assertion) and ## Scope

- `fabricate no old-version fixture`
- `src/aeat/_data/compat_fixtures` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Ship the empty cross-version fixture-corpus harness (directory + vacuous coverage assertion)

## Scope

- `fabricate no old-version fixture`
- `src/aeat/_data/compat_fixtures`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in commit ffb2f94605 - dormant compatibility-lifecycle mechanism: core regime module (enum + one-way COMPATIBILITY_REGIME=PRE_RELEASE + RELEASED_FORMAT_FLOORS=None + pure expected_floor/lineage_obligations predicates), regime-aware tier gates (behaviour-identical today), synthetic RELEASED-branch tests, central tripwire/coherence/enrollment gate, empty fixture harness. 34 passed, dormant confirmed.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
