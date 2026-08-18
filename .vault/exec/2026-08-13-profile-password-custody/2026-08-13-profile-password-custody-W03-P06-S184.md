---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:dfc0b2f4fbf473b52c8b07cb66c77ac3cf25cd50eaea19073b1928c66d6fde53'
step_id: 'S184'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S184 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium rule whether the profile subject of the bucket history verb was meant to become optional, since the live command now yields an empty required-input set while the profile parameter is still declared, so a schema test asserting the subject is required fails on a key error and nothing swept it when the change landed, and a single-subject verb losing its required subject is either a deliberate widening nobody recorded or an accidental one that changes what the operator must supply and ## Scope

- `src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/entrypoints/cli/tests/test_verb_input_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium rule whether the profile subject of the bucket history verb was meant to become optional, since the live command now yields an empty required-input set while the profile parameter is still declared, so a schema test asserting the subject is required fails on a key error and nothing swept it when the change landed, and a single-subject verb losing its required subject is either a deliberate widening nobody recorded or an accidental one that changes what the operator must supply

## Scope

- `src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/entrypoints/cli/tests/test_verb_input_schema.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Ruled: the bucket-history subject widening was deliberate (part of the d18e37c274 verb rework to bucket-scoped reads with an active-profile fallback; the operator help already documents `[PROFILE]`). The schema test now reads `profile` from the live parameter metadata, asserts `required is False` and `required_inputs == ()`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
