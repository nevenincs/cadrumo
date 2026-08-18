---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:a686917d285322e45bbd996a15e2283473e51fa4779caa79ecbe8ab5328297f7'
step_id: 'S153'
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
     The S153 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium rule whether a legal entity may be registered with no legal form, since the retired creation path enforced that requirement while no surviving surface enforces it and the registry schema declares the field not required, and the field's own description says it drives the corporate tax rate schedule under the cited article so an entity can now be established with no selector for its rate schedule and ## Scope

- `src/cadrumo/_data/registry/ and src/cadrumo/application/user_profile/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium rule whether a legal entity may be registered with no legal form, since the retired creation path enforced that requirement while no surviving surface enforces it and the registry schema declares the field not required, and the field's own description says it drives the corporate tax rate schedule under the cited article so an entity can now be established with no selector for its rate schedule

## Scope

- `src/cadrumo/_data/registry/ and src/cadrumo/application/user_profile/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Ruled: registry `required=true` on the legal-form field is wrong — the requirement is conditional on `entity_type == legal_entity`. Enforcement now lives in `conditional_profile_required_paths` (`application/user_profile/_completeness.py`): a profile declaring the legal-entity type owes `taxpayer_type.legal_entity_form`, propagating to fact-write keys, conditional issues and the filing baseline (whose explicit legal-form branch stays for the legal-name companion). Registration remains permissive by design — a profile is born INCOMPLETE.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
