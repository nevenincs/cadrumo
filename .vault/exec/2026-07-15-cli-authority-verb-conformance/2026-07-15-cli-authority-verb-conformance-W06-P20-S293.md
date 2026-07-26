---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S293'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S293 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Escalate to the owning TUI campaign that the committed wizard package initialiser imports an untracked results module, so a clean checkout of HEAD cannot import the wizard or run the shipped CLI and ## Scope

- `src/cadrumo/application/wizard/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Escalate to the owning TUI campaign that the committed wizard package initialiser imports an untracked results module, so a clean checkout of HEAD cannot import the wizard or run the shipped CLI

## Scope

- `src/cadrumo/application/wizard/__init__.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Escalate that the committed wizard package initialiser imports an untracked
module, so a clean checkout cannot import the wizard or run the shipped CLI.

## Outcome

SATISFIED, resolved by its owner before the escalation was delivered.

The committed package initialiser carried a module-level import of a results
module that was untracked, added by a TUI campaign commit that landed the
importer without the module. The file existed in every active agent's working
tree, so the package imported for everyone here and could not import from a
clean checkout. The CLI root reaches wizard submodules, so the shipped CLI
inherited it.

Invisible by construction: no agent in this worktree could observe it, because
every agent had the file. Only a clean checkout, a fresh clone or an installed
distribution sees it.

Fixed by the owning campaign at `b482927401`. Verified empirically rather than
by file presence: a tree extracted with `git archive` carrying no untracked
files at all imports the wizard package and exports the result classes.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
