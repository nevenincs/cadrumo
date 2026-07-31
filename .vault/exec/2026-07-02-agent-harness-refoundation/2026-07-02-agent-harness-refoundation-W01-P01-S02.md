---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:2ee89ac731945f7e12bc45c3a32b00c67fdaf0f09bec7f514b219f6ec3061e99'
step_id: 'S02'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Consume per-verb input schemas in build_tool_descriptors and retire the _ARGS_INPUT_SCHEMA bag

## Scope

- `src/aeat/entrypoints/mcp/_tools.py`

## Description

- Add a `verb_schema` field to `McpToolDescriptor` and render its `input_schema` from the per-verb schema, retiring the shared `_ARGS_INPUT_SCHEMA` bag in `_tools.py`.
- Build the per-verb schemas once from the exposable command keys and attach each to its descriptor.
- Wire the server subprocess dispatch to reconstruct argv from the descriptor's `verb_schema` and the named client arguments via `cli_argv_for`, dropping the `arguments["args"]` bag read in `_server.py`.
- Update the tool-descriptor tests: assert every descriptor carries a non-bag per-verb schema equal to its structured projection, and drive argv from the schema.

## Outcome

Every exposed descriptor now advertises a typed per-verb input schema instead of the `{args: [string]}` bag, and the live serving path builds a correct argv from named arguments through the resolved CLI path. The mcp suite is green at 48 passed, and the determinism-replay eval stays green. Ruff check/format clean; the only pyright diagnostic on the touched files is the pre-existing dynamic-re-export typing of `command_schema_refs`, present identically at HEAD.

## Notes

`tool_request_argv` and `_cli_path_tokens` are deliberately retained in `_dispatch.py`: the determinism-replay eval reconstructs argv from recorded raw-token calls (`GoldenToolCall.args`), whose shape is W04 scope to change, so the plan's "retire the bag" intent is satisfied by removing `_ARGS_INPUT_SCHEMA` and the server's bag acceptance rather than deleting that mapper.

Process deviation: the shared worktree carried peer docstring WIP on `_server.py`. My server hunks were staged HEAD-anchored via `git apply --cached` (verified zero peer markers), but the closing `git commit -- <pathspec>` re-stages the working tree for the named path, so a peer's four-line additive docstring in `filter_descriptors_for_persona` rode into the commit. No work was lost and no other peer-staged files were swept (the commit is exactly the four intended files); the peer's docstring is committed as valid content. `_server.py` is now clean at HEAD, so later steps start unentangled.
