---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S09'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them and ## Scope

- `justfile`
- `dev/docs/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them

## Scope

- `justfile`
- `dev/docs/tests`

## Description

- Confirm the docs-check lane enrolls the localization gates: the lane already globs the `dev/docs/tests` directory and filters by the `docs` marker, and the new gates carry that marker.
- Run `pytest --collect-only` under the exact docs-check invocation to verify collection.

## Outcome

The exact docs-check collection surfaces every new gate: the completeness parametrization, the parity gate, and the per-language build matrix. No justfile change was required because the lane globs the test directory and the gates carry the `docs` marker. `pytest --collect-only -q dev/docs/tests` is clean.

## Notes

The docs-check lane is now expected red until the translation wave lands, driven solely by the completeness gate. Every other gate the wave touched is green.
