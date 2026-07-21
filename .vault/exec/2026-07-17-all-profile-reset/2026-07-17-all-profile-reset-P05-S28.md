---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S28'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Migrate the four locale catalogues for the reset and sandbox families through the locales CLI and ## Scope

- `src/cadrumo/locales/en.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the four locale catalogues for the reset and sandbox families through the locales CLI

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Through the locales manager (the same code path the `set`/`remove`/`scaffold` CLI verbs use), scaffold the three new `cli.operator_surface.help.config.reset_{start,status,resume}` keys into all four catalogues and set each locale's value from the already-translated `cli.config.reset.*_help` copy.
- Remove the orphaned `cli.config.profile.sandbox.use_help` / `use_name_help` leaves from all four catalogues (the `sandbox use` verb was deleted in S19).

## Outcome

`scaffold --check` reports ok for en/es/ca/hu; the reset CLI verb keys were already present from S26/S21. Parity, translation-honesty, and coverage-inventory gates green (35 passed). The catalogues were edited only through the manager API, never by hand.

## Notes

Routed the `set` values through the manager in-process (reading the existing translated verb-help strings) rather than passing accented es/ca/hu text as shell argv, avoiding console-encoding corruption while staying on the sanctioned CLI code path.
