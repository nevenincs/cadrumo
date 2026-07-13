---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S21'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Remove the tracked repo-root run artifacts from version control and ## Scope

- `repo-root run artifacts` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the tracked repo-root run artifacts from version control

## Scope

- `repo-root run artifacts`

## Description

- Read each of the five tracked repo-root files to confirm genuine
  run-artifact provenance before removal: `add_frontmatter.py` (an ad-hoc
  docs frontmatter-injector script), `rail-snap.md` (a Playwright
  accessibility-tree snapshot dump), `revert.patch` (a captured git diff from
  an earlier revert/apply-cached run), `scratch_pathspec.txt` (an empty
  pathspec probe), `test_docs_output.txt` (a captured docs-gate command log).
- `git rm --cached` all five, leaving working-tree bytes untouched (per the
  git-worktree-safety and no-destructive-delete disciplines).

## Outcome

- All five paths now match a `W04.P07.S20` gitignore pattern
  (`git check-ignore -q`), so `git status` shows no stray untracked entries
  after the cached removal.
- Working-tree bytes for all five files are preserved on disk; only the git
  index entries were removed.

## Notes

None.
