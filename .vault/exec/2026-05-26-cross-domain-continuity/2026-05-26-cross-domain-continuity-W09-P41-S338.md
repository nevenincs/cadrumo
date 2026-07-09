---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S338'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S338 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The CRITICAL incident log  -  S278 commit c25b14a54 + c94ed9a38 used HEAD-based reconstruction + restore pattern to isolate from peer WIP per coder1 step record and ## Scope

- `functionally equivalent to forbidden git-discipline operations`
- `the correct cross-commit pattern is git commit -- only-my-files with cross-authorship note in message never separation by destructive means`
- `code content stands no rollback (rolling back would itself be destructive)`
- `incident is the process not the code`
- `.vaultspec/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# CRITICAL incident log  -  S278 commit c25b14a54 + c94ed9a38 used HEAD-based reconstruction + restore pattern to isolate from peer WIP per coder1 step record

## Scope

- `functionally equivalent to forbidden git-discipline operations`
- `the correct cross-commit pattern is git commit -- only-my-files with cross-authorship note in message never separation by destructive means`
- `code content stands no rollback (rolling back would itself be destructive)`
- `incident is the process not the code`
- `.vaultspec/`

## Description

- Record the critical git-discipline incident: S278 commits c25b14a54 and c94ed9a38 used a HEAD-based reconstruction-and-restore pattern to isolate authored work from peer WIP, a technique functionally equivalent to the forbidden destructive git operations.
- Confirm the durable lessons are codified as standing project rules: `uncommitted-wip-is-not-orphaned` (never discard or overwrite live peer WIP; land your own change with the apply-cached gated drive) and `aeat-git-worktree-safety` (the categorical prohibition on stash/reset/restore/checkout-path in the shared worktree).
- No production-code change and no rollback: the incident is process, not code; the committed content stands, and reverting a peer commit would itself be a forbidden destructive operation.

## Outcome

Doc-only closure. The correct cross-commit pattern (`git commit -- <only-my-files>` with a cross-authorship note in the message, never separation by destructive means) is now a session-inherited rule pair binding every future dispatch. Companion rule: `subagent-commits-require-explicit-pathspec` (the S311 sibling).

## Notes

Closed by codification, not by a commit. The two rules already ship in `.vaultspec/rules/rules/`; this record ties the S338 finding to them so the plan-closure-requires-exec-records contract is satisfied.
