---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f3b819987e91a2b4495536a4a879581e5588ab3df11774dd94a9595abc11fcb3'
step_id: 'S165'
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
     The S165 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh establish why a durably written profile record fails its object-key comparison in a fresh process when the digest is deterministic given the DEK, testing first whether the record is written under the short-lived staging session the capsule repository opens before a capsule is published and therefore keyed under a digest the later published session cannot reproduce, and correct the refusal message which reports only the count half of a two-part condition while the key half is what fails and ## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/user_profile/_capsule_record.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh establish why a durably written profile record fails its object-key comparison in a fresh process when the digest is deterministic given the DEK, testing first whether the record is written under the short-lived staging session the capsule repository opens before a capsule is published and therefore keyed under a digest the later published session cannot reproduce, and correct the refusal message which reports only the count half of a two-part condition while the key half is what fails

## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/user_profile/_capsule_record.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
