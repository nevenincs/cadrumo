---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:db16e2fa4cc5dcb6796f811e3e1c442cc98536cc0994dcd23643c1135ee5191f'
step_id: 'S145'
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
     The S145 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh sever the dependency cycle between the core distribution and the extracted harness by moving the four harness-delivery surfaces into the harness package and dropping the core dependency, since the harness project file states that it consumes the core library and never the reverse while a repair added exactly that reverse edge, making the current shape a deliberate temporary the sever supersedes and ## Scope

- `pyproject.toml and src/cadrumo/entrypoints/ and src/cadrumo-harness/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh sever the dependency cycle between the core distribution and the extracted harness by moving the four harness-delivery surfaces into the harness package and dropping the core dependency, since the harness project file states that it consumes the core library and never the reverse while a repair added exactly that reverse edge, making the current shape a deliberate temporary the sever supersedes

## Scope

- `pyproject.toml and src/cadrumo/entrypoints/ and src/cadrumo-harness/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
