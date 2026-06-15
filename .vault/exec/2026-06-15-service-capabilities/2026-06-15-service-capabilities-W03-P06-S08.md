---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Add aeat config doctor: per-service availability + active-profile capability posture + remediation and ## Scope

- `typed envelope + non-zero exit on opted-in-but-missing`
- `src/aeat/entrypoints/cli/_config` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add aeat config doctor: per-service availability + active-profile capability posture + remediation

## Scope

- `typed envelope + non-zero exit on opted-in-but-missing`
- `src/aeat/entrypoints/cli/_config`

## Description

- Add `aeat config check`: per-service dependency availability (probes) + the active profile's capability posture (resolver) + remediation, exiting non-zero when an opted-in capability has a missing dependency; typed payload + locales; CLI test. Named `check` because `config doctor` is a retired path.

## Outcome

One command reports the capability/dependency/safety axes together with the fix per gap.

## Notes

Resilient to a locked secret store (falls back to defaults). Avoid on/off as locale key leaves (YAML boolean coercion); reused the capabilities enabled/disabled keys.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
