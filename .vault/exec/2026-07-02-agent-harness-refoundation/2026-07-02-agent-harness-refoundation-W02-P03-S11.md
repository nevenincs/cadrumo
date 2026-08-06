---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:4204bd4b9f13e30e6a89bb92a199f6cab7fd80b8844a291053f08df9a8a7ced8'
step_id: 'S11'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

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
