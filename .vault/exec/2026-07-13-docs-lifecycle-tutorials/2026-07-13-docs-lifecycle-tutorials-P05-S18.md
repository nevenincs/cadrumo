---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S18'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Retire the three stray project-management files from the docs root (ADRS.md, USERDOCS-KICKOFF-BRIEF.md, HARNESS-USERDOCS-KICKOFF-BRIEF.md) per docs-architecture ADR clause 3a

## Scope

- `docs/ADRS.md docs/USERDOCS-KICKOFF-BRIEF.md docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md`

## Description

- Inspect all three files before removal: the two `*KICKOFF-BRIEF.md` files
  are agent-process kickoff briefs ("hold for the operator's instruction"),
  and `ADRS.md` is a hand-maintained ADR index - all three are
  project-management/process metadata in the shipped docs tree, barred by
  the docs-architecture ADR clause 3a and `aeat-source-hygiene`.
- Verify safety: all three are committed (not peer WIP - `git status` clean
  for the paths), carry zero inbound references from any docs page, and no
  generator under `dev/`, `pyproject.toml`, or `justfile` owns `ADRS.md`.
- Delete all three via `git rm`; content remains recoverable from git
  history, and `.vault/adr/` stays the ADR authority.

## Outcome

The docs root carries no process metadata. Surfaced by the campaign-close
honesty review (finding 3), tracked as this step, closed with the deletion.

## Notes

`docs/ADRS.md` originally landed via a governance chore commit
(`835c80f17d`); if a public ADR index is wanted later, it should be a
generated artifact, not a hand-maintained docs-tree file.
