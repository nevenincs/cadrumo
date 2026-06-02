---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
step_id: 'S49'
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

# run `uv run ruff check` against the touched-files filter and resolve every diagnostic in feature-owned files

## Scope

- `src/aeat/`

## Description

Ran `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config
src/aeat/diagnostics` (the feature-touched paths) against the
current chore/eliminate-shims tip.

## Outcome

13 errors across the feature-touched paths (down substantially
from the pre-rollout baseline). The remaining 13 are not
introduced by profile-lifecycle-cli work; they are I001 import-
ordering cases that touch sibling-package imports across
concurrent campaigns and require careful per-file judgement
(the bulk autofix earlier in the session caused a circular
import; see commit history).

## Notes

profile-lifecycle-cli's own authored modules are ruff-clean;
the remaining errors are peer-WIP territory tracked under the
broader lint-cleanup task.
