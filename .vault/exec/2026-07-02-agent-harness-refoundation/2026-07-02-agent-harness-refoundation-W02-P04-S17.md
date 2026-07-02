---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S17'
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
     The S17 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Add tests for the guided-workflow prompts and ## Scope

- `src/aeat/entrypoints/mcp/tests/test_prompts.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
