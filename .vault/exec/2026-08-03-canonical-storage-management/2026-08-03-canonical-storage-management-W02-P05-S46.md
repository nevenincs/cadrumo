---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:8672b73b1098a7b6e09c112489a71a7b93beba32252672d277740cde980cf4b1'
step_id: 'S46'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S46 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Declare the Playwright browser root as a third-party-owned-cache escape carrying its role, gated by a test asserting the escape is declared and that the resolver still honours the vendor environment variable and ## Scope

- `src/cadrumo/application/provisioning.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the Playwright browser root as a third-party-owned-cache escape carrying its role, gated by a test asserting the escape is declared and that the resolver still honours the vendor environment variable

## Scope

- `src/cadrumo/application/provisioning.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `b3015bda3e`, confirmed at HEAD. `PLAYWRIGHT_BROWSERS_ROOT_ROLE = ExternalPathRole.THIRD_PARTY_CACHE` in `src/cadrumo/application/provisioning.py:168` declares the escape with a docstring explaining Playwright's vendor-owned layout (lines 169-183). Gated by `application/tests/test_provisioning.py`, confirmed to still honour the vendor environment variable.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
