---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace agent-harness-refoundation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Demote the workspace materialiser to an optional Claude-native .claude/skills mirror layout and ## Scope

- `src/aeat/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Demote the workspace materialiser to an optional Claude-native .claude/skills mirror layout

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Rewrite `materialise_workspace` in `src/aeat/agent/_workspace.py` to emit the Claude-native mirror layout, replacing the flat `{rules,personas,skills}/` layout (no-legacy: the flat layout is deleted, not kept).
- Skills -> `.claude/skills/<name>/SKILL.md` plus each skill's `reference/` subtree (via the retained `_copy_skill`).
- Personas -> `.claude/agents/<name>.md` (Claude Code subagent definitions).
- Operator rules -> `.claude/rules/<name>.md`, aggregated by a new `_claude_memory` helper that writes a root `CLAUDE.md` importing every rule with `@.claude/rules/<name>.md` lines.
- Keep the `WorkspaceManifest` schema (output_path + three counts); document that `CLAUDE.md` is derived from the rules and not separately counted.

## Outcome

Layout decision recorded and implemented. Smoke check against a real tmp dir: 7 rules, 7 personas, 34 skills written; `CLAUDE.md` present at root and imports `@.claude/rules/operator-grounding.md`; `.claude/skills/preparar-modelo-130/SKILL.md` and its `reference/casillas.md` present; `.claude/agents/coordinator.md` present; the old flat `rules/` and `skills/` directories are absent. Ruff, ruff-format, pyright clean.

## Notes

CLAUDE-NATIVE LAYOUT DECISION (per S15's decision mandate): skills use the standard `.claude/skills/<name>/SKILL.md`; personas map to `.claude/agents/<name>.md` (Claude Code's subagent home); operator rules go to `.claude/rules/<name>.md` and are made always-on by a root `CLAUDE.md` that `@`-imports each rule — Claude Code auto-loads `CLAUDE.md` at session start and resolves `@path` as imports, mirroring how this very repo composes its rule set. This is a REPLACEMENT (the prior flat layout is deleted). The existing `test_workspace.py` asserts the old flat layout and is therefore red at this commit; it is rewritten immediately in S18 (paired here for a coherent surface). S18 was landed directly after S15 rather than after S16 for that reason.
