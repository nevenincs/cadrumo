---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9b875a75560f4624b5b8b1378c6cbde34c751087ecf983005e959824b15d07f3'
step_id: 'S15'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

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
