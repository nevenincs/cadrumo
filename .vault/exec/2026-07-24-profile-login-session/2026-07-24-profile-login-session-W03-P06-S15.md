---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S15'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-login-session with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-24-profile-login-session-plan placeholders are machine-filled by
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
     The Sever the environment source for cadrumo_active_profile so the field is populated only by --profile and override_settings, retarget the logout override refusal to the per-invocation --profile case, and sweep every string or doc naming CADRUMO_ACTIVE_PROFILE as an operating mechanism, verified by a settings test proving the env var no longer selects a profile and the existing override-refusal tests retargeted green and ## Scope

- `src/cadrumo/core/config.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/application/user_profile/_orchestration.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sever the environment source for cadrumo_active_profile so the field is populated only by --profile and override_settings, retarget the logout override refusal to the per-invocation --profile case, and sweep every string or doc naming CADRUMO_ACTIVE_PROFILE as an operating mechanism, verified by a settings test proving the env var no longer selects a profile and the existing override-refusal tests retargeted green

## Scope

- `src/cadrumo/core/config.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/application/user_profile/_orchestration.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
