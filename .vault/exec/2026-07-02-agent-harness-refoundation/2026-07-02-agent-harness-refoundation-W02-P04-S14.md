---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Wire the prompt list and get handlers into the server

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Import the coordinator-authored `_prompts.py` surface (`build_prompt_catalogue`, `prompt_document`, `PromptNotFoundError`) into `_server.py`.
- Add `EmbeddedResource`, `PromptMessage`, `TextResourceContents` to the SDK type imports in `build_server`.
- Replace the empty `list_prompts` handler with one that adapts every `build_prompt_catalogue()` row to an SDK `Prompt` (no arguments).
- Replace the empty `get_prompt` handler: resolve `prompt_document(name)`, emit the operating brief as a user `TextContent` message followed by one user `EmbeddedResource` message per embedded document (`TextResourceContents` carrying the verbatim skill/rules text and `text/markdown` mime), and map `PromptNotFoundError` to a protocol `ValueError`.
- Update the module and `build_server` docstrings to state prompts are now served.

## Outcome

The guided-workflow prompt channel is live on the built server. Smoke check through the real registered SDK handlers (with an empty descriptor set to sidestep the peer-broken CLI import — see Notes): `prompts/list` returns 35 prompts (34 skills + orientation); `prompts/get` for `preparar-modelo-130` returns a text brief message plus an `EmbeddedResource` message whose resource URI is `aeat://skill/preparar-modelo-130` at `text/markdown`; the orientation prompt embeds the operator rules; an unknown name raises `ValueError`. Ruff and pyright clean.

## Notes

The W02 phase-end gate `pytest src/aeat/entrypoints/mcp src/aeat/agent` is red from an UNRELATED peer-owned break: a peer's uncommitted deletion of `TransactionParticipationIndexRepository` in `domain/modelos/_participation_index.py` (124 lines removed in the working tree) breaks the shared CLI import chain, so any test transiting `build_tool_descriptors()` fails with `ImportError`. Not my surface; not touched (uncommitted peer WIP). Prompt-handler verification was done with `build_server(())` (empty descriptors), which does not transit the broken import. Full-gate re-run and S12 closure are pending the peer relocation landing.
