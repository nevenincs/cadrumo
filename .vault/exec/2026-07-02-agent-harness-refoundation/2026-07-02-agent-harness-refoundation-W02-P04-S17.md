---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:efe64ff25cbaa5677fcb0347eda002c6944189eeac6f7de6dbe892ef5b4d6214'
step_id: 'S17'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add tests for the guided-workflow prompts

## Scope

- `src/aeat/entrypoints/mcp/tests/test_prompts.py`

## Description

- Add `src/aeat/entrypoints/mcp/tests/test_prompts.py` with SDK-independent assertions over `_prompts.py` and server-driven assertions over the wired handlers.
- Assert the catalogue is exactly the 34 shipped skills plus the orientation entry.
- Assert every skill prompt embeds its `SKILL.md` verbatim as an `aeat://skill/<name>` `text/markdown` resource and carries a non-empty operating brief.
- Assert the orientation prompt embeds `operator_rules_text()` verbatim.
- Assert an unknown prompt name raises `PromptNotFoundError` (pure) and maps to a `ValueError` protocol error through the server `get_prompt` handler.
- Drive `prompts/list` and `prompts/get` through the real built `Server` using an empty descriptor set so the prompt channel is exercised without transiting the CLI tool-descriptor import chain.

## Outcome

7 tests pass; ruff and pyright clean. The prompt channel is proven end to end through the registered SDK handlers: list returns the 35-entry catalogue, get returns the brief message plus embedded skill/rules resources verbatim, and an unknown name is a clean protocol error.

## Notes

The server-driven tests build with `build_server(())` (empty descriptors) deliberately: this exercises the prompt handlers while sidestepping the peer-owned `TransactionParticipationIndexRepository` import break in the CLI tool-descriptor chain (see the S14 record), so this test file is fully green independent of that peer WIP.
