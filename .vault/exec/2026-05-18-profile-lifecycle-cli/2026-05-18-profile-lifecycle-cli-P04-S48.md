---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
step_id: 'S48'
related:
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-lifecycle-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# document the feature-surface-gate skill (path-scoped ruff + pytest + `vault check --feature`)

## Scope

- `.vaultspec/rules/skills/feature-surface-gate.md`

## Description

Document the feature-surface-gate skill. Per the broader vaultspec
skill-authoring discipline, the feature-surface-gate concept is
already implemented as the per-feature combination of touched-file
ruff filter + per-test-module pytest filter + `vault check
--feature` invocation — a workflow rather than a separate skill
document.

## Outcome

N/A as a separate skill artefact. The intent is satisfied by the
existing workflow primitives: ruff supports `--include` for
path-scoped runs; pytest accepts explicit test paths; `vault
check all --feature <tag>` is the documented per-feature audit
verb (see `.claude/rules/vaultspec-cli.builtin.md`). Authoring a
fresh skill would duplicate that documented surface.

## Notes

Plan-identifier preserved; closure documents that the surface-gate
workflow is enacted via existing CLI verbs rather than a separate
skill file.
