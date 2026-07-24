---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S28'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test and ## Scope

- `src/cadrumo/application/user_profile/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test

## Scope

- `src/cadrumo/application/user_profile/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Re-enrol the dormant `CENSO_APPLIED` bucket event: `ProfileLifecycleService.record_censo_applied` is the single live emission site, called exactly once per apply-commit by `apply_cotejo` regardless of fact count, read back from the real event history repository in every apply-shaped test.
- Close the second-write-route hole the review adjudicated: `config profile censo file --apply` routes through the same apply authority instead of a bare fact write, so a censal artefact-apply can never persist silently without its audit event; the door's docstring now names the authority and the emission.

## Outcome

Landed as `8f004fcc51` with the routing fix in `c253a117c2` and the documentation-and-pin follow-up `4e51620cf8`. The emission is pinned fact-count-independent, the adopt-all door shape emits exactly one event, and the lifecycle docstring's claim about the file door is true at HEAD.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The event is live-dormant with the rest of the cotejo family until a G313 specimen pins the parser; the emission contract is fully tested against synthetically constructed certificates through the real encrypted write path.
