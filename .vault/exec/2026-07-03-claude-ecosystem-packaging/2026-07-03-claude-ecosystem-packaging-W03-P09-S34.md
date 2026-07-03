---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S34'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S34 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add the anthropic/requiresUserInteraction annotation to CONFIRM-tier (state-mutating) MCP tools alongside the existing destructiveHint matrix and ## Scope

- `src/aeat/entrypoints/mcp/_annotations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the anthropic/requiresUserInteraction annotation to CONFIRM-tier (state-mutating) MCP tools alongside the existing destructiveHint matrix

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Stamp `_meta={"anthropic/requiresUserInteraction": true}` on every SDK tool `build_sdk_tools` emits whose `confirmation_for_tool(...)` resolves to `ConfirmationPolicy.CONFIRM`.
- Derive the stamped set from the existing single-authority mutability classification; no hand-listed tool names.
- Leave every non-CONFIRM tool without a `_meta` entry, alongside the existing `destructiveHint` matrix.
- Commit `f178141b73`.

## Outcome

- `src/aeat/entrypoints/mcp/_server.py` changed by 14 insertions / 1 deletion, wiring the `requires_user_interaction(policy)` helper from `S33` into tool construction.

## Notes

The plan Step row names `src/aeat/entrypoints/mcp/_annotations.py` as the scoped file; the implementation lands in `src/aeat/entrypoints/mcp/_server.py`, the module that already owns `build_sdk_tools` and the existing `destructiveHint` annotation matrix this step extends. No incidents. No skipped work.
