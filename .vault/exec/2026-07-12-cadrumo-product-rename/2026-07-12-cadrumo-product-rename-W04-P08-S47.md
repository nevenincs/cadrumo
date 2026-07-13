---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S47'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S47 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Prove a real Cadrumo client initialize, list, call, and shutdown handshake and ## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove a real Cadrumo client initialize, list, call, and shutdown handshake

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py`

## Description

- Spawn the installed/current `cadrumo-mcp` executable through the real MCP stdio client.
- Initialize the session and enumerate resources, resource templates, prompts, and tools.
- Assert canonical Cadrumo identities and reject the former product identity across every wire surface.
- Call the shipped read-only harness tool and close both client and subprocess contexts cleanly.

## Outcome

The live handshake proves the Cadrumo server name, `cadrumo://` resource
identity, `cadrumo-empezar` orientation prompt, `cadrumo_` tool identity, a
successful safe tool round trip, and orderly shutdown. Both focused integration
tests and Ruff checks pass.

## Notes

The existing in-process probe originally called the CLI-backed contract tool,
which intermittently depended on a second executable being present on `PATH`.
It now calls the same shipped read-only harness floor as the stdio proof, keeping
the test focused on MCP transport behavior without substitutes.
