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

# Escalate to the owning TUI campaign that the committed wizard package initialiser imports an untracked results module, so a clean checkout of HEAD cannot import the wizard or run the shipped CLI

## Scope

- `src/cadrumo/application/wizard/__init__.py`

## Description

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
