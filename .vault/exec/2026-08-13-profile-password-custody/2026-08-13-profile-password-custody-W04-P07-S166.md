---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f4e8e8cfe897fa581f96707235ed45d508ffe310301612c58682197632d6af2a'
step_id: 'S166'
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
     The S166 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh compose the full-corpus collectability proof into a lane that is actually run, since the harness that would have caught two test packages being uncollectable is real and mutation-tested but is enrolled only in a standalone recipe every other lane ignores and in a single separately-named continuous-integration job, so every routine local and integration run stayed green throughout the window those packages could not import, and a green lane structurally unable to see a collection error is what makes one read as infrastructure noise and get scrolled past and ## Scope

- `justfile and .github/workflows/ci.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh compose the full-corpus collectability proof into a lane that is actually run, since the harness that would have caught two test packages being uncollectable is real and mutation-tested but is enrolled only in a standalone recipe every other lane ignores and in a single separately-named continuous-integration job, so every routine local and integration run stayed green throughout the window those packages could not import, and a green lane structurally unable to see a collection error is what makes one read as infrastructure noise and get scrolled past

## Scope

- `justfile and .github/workflows/ci.yml`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
