---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S16'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Update the app-agent workspace CLI to emit the Claude-native mirror

## Scope

- `src/aeat/entrypoints/cli/_app_agent_workspace.py`

## Description

- Update the module docstring of `src/aeat/entrypoints/cli/_app_agent_workspace.py` to describe the Claude-native mirror layout the verb now emits (`.claude/skills`, `.claude/agents`, `.claude/rules`, root `CLAUDE.md`) and to state it is the optional Claude-native mirror while the MCP console is the primary client-agnostic channel.
- Update the `cli.agent.app_help` and `cli.agent.materialise.output_help` help strings across en/es/ca/hu via the `aeat.locales set` CLI to name the Claude-native `.claude` output.

## Outcome

The CLI verb already emitted the mirror (it calls `materialise_workspace`, rewritten in S15); this step makes the operator-facing surface describe it. The verb docstring is updated and committed. The four-locale help-string updates are in HEAD (see Notes) and pass the locale parity + honesty gates (22 tests green). The `--json` `AgentWorkspaceResult` schema and the emitted summary are layout-agnostic (path + counts) and needed no change.

## Notes

Shared-file contention on the locale catalogues: my `aeat.locales set` updates to the four locale files repeatedly raced against a peer's concurrent W03 locale work (the elicitation/faithfulness/handoff keys), which re-serialized the same files. My working-tree agent-key edits were ultimately swept into HEAD by the peer's W03 commit `2ba6d656f4` (all four locales carry the Claude-native `app_help`/`output_help` in HEAD, verified). I did not commit any locale file under my SHA (an apply-cached attempt found the files already clean at HEAD). No locale content was lost. The verb file carries one pre-existing pyright `object-not-callable` note on `materialise_workspace`, an artefact of the `aeat.agent` facade's lazy `__getattr__` re-export; it predates this docstring-only change and cannot be resolved without importing the internal `_workspace` submodule, which `service-imports-via-top-level-reexports` forbids for production code.
