---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:9cf0a7b3c232beb3b91d7922fff370d3b6202a689999fba9f42274efba8cb209'
step_id: 'S201'
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
     The S201 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium rule whether a refusal message may be keyed on a field inside one exception class, since the four distinct profile-custody refusal reasons all resolve to a single shared sentence because the error registry keys by exception class alone, so the specific cause and its recovery guidance reach the operator only as structured context and never as differentiated prose, and no existing registry entry keys on an inner field so this is a design question rather than a missing catalogue value and ## Scope

- `src/cadrumo/core/errors/registry/ and src/cadrumo/adapters/persistence/storage/custody/_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium rule whether a refusal message may be keyed on a field inside one exception class, since the four distinct profile-custody refusal reasons all resolve to a single shared sentence because the error registry keys by exception class alone, so the specific cause and its recovery guidance reach the operator only as structured context and never as differentiated prose, and no existing registry entry keys on an inner field so this is a design question rather than a missing catalogue value

## Scope

- `src/cadrumo/core/errors/registry/ and src/cadrumo/adapters/persistence/storage/custody/_errors.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Ruled AGAINST field-aware registry keying: the registry binds by exception class at class-creation, and the instance `translated_message` channel is the existing per-instance differentiation (resolution precedence: instance translated_message → args[0] → class message_key). `ProfileCustodyRefusedError` now accepts `translated_message` and the three live raise sites carry reason-specific keys (`errors.refused.refused_profile_custody_legacy`, `..._kdf_resource_limit`, `..._kdf_supervision_unavailable`), authored in all four catalogues via the locales CLI. The class registry row stays as fallback.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
