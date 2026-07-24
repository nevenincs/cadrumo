---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S28'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Run the locale parity, translation honesty, and scaffold check gates green for the substrate key namespaces and ## Scope

- `src/cadrumo/locales/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the locale parity, translation honesty, and scaffold check gates green for the substrate key namespaces

## Scope

- `src/cadrumo/locales/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Run the locale test suite: parity, translation honesty, dynamic-prefix registry coverage, placeholder self-echo, and language-override inventory gates all green for the substrate namespaces (44 passed).
- Run the scaffold drift check; remove the two orphaned wizard answer-queue error leaves the prompter retirement left behind, through the locales CLI across all four catalogues, and land the removal as its own explicit-pathspec commit.
- Re-run the drift check: zero extras remain.

## Outcome

Every substrate key namespace (`flows.*`, `application.flows.*`, `wizard.*`, the status-page and copy-slot registrations) is green across parity, honesty, coverage, and drift gates. The orphaned-leaf cleanup previously deferred to a post-merge sweep was retired early in the same pass.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Owner triage: the remaining drift-check and audit reds are one missing key, `application.wizard.notices.modify_descendants_via_door`, referenced by a peer campaign's uncommitted descendant-door notice; the peer sets that key in their commit. No substrate namespace is affected.
