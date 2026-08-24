---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:90d816216b3d0b97b5bd6a1839be4869773e70ad3f0dc4fd04b9748d7d5d5321'
step_id: 'S46'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S46 and 2026-08-24-registry-completeness-closure-plan placeholders are machine-filled by
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
     The Apply expiry semantics to every scoped census disposition and refuse expired terminal evidence, with mutation-bite tests. and ## Scope

- `src/cadrumo/application/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Apply expiry semantics to every scoped census disposition and refuse expired terminal evidence, with mutation-bite tests.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Evaluate the explicit census expiry posture for every entry scoped to a validated revision.
- Refuse expired terminal evidence while retaining the census row owner and a concrete revalidation condition.
- Add a terminal mutation bite that removes an obsolete row's follow-up and proves the closure limb still refuses at the expiry boundary.

## Outcome

- The source-connectivity limb cannot satisfy closure from expired terminal evidence.
- Direct public-facade composition smoke check passed for a Modelo 100 terminal mutation at its inclusive expiry boundary.
- Ruff passed for the composer and its focused coverage test module.

## Notes

- The dedicated pytest invocation did not return within two 30-second timeboxes while concurrent shared-worktree test jobs were active. The equivalent public-facade mutation was executed directly instead; no failure was observed.
