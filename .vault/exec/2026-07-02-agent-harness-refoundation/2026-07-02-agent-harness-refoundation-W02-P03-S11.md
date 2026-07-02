---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S11'
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
     The S11 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Wire the resource list and read handlers into the server and ## Scope

- `src/aeat/entrypoints/mcp/_server.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Wire the resource list and read handlers into the server

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Import the S09 floor tool (`build_harness_floor_tool`, `build_harness_floor_payload`, `render_harness_floor_text`, `HARNESS_LOAD_TOOL`) and the S10 resource functions (`list_harness_resources`, `list_harness_resource_templates`, `read_harness_resource`, `HarnessResourceNotFoundError`) into `_server.py`.
- Advertise the floor tool first in `_list_tools`, ahead of the per-verb and meta tools; it is never persona-scoped away (the universal ADR R4 channel).
- Route `HARNESS_LOAD_TOOL` in `_call_tool` before the persona/HITL gate: build the floor payload from the server's resolved persona and return it as text plus structured content (read-only, always available).
- Replace the empty `list_resources`/`read_resource` handlers with real ones and add a `list_resource_templates` handler: concrete `aeat://` resources, the three templates, and a `read` resolver mapping `HarnessResourceNotFoundError` to a protocol `ValueError`.
- Update the module docstring to state resources are now served and prompts remain empty until S14.

## Outcome

Floor tool and resource pull channel are live on the built server. End-to-end through the real registered SDK request handlers: `tools/list` advertises `aeat_harness_load` (235 tools total), `resources/list` returns 48 concrete resources, `resources/templates/list` returns the three `aeat://<kind>/{name}` templates, and `resources/read` on `aeat://persona/verifier` returns the verbatim document as `text/markdown`. The full `src/aeat/entrypoints/mcp` suite is green (70 passed). Ruff and pyright clean.

## Notes

Renamed the floor branch's local from `payload` to `floor_payload` to avoid a pyright variable-type collision with the later annotated `payload: dict[str, object]` in the `search` meta-tool branch (an annotated assignment types the name for the whole function scope). `read_resource` returns `list[ReadResourceContents]` (from `mcp.server.lowlevel.helper_types`) so the `text/markdown` mimeType is carried, rather than a bare `str` which the SDK would default to `text/plain`.
