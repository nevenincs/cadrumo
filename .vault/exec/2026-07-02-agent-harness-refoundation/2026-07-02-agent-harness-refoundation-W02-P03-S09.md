---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S09'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the harness.load floor tool returning operator rules and the active persona via aeat.agent

## Scope

- `src/aeat/entrypoints/mcp/_harness_tools.py`

## Description

- Add `src/aeat/entrypoints/mcp/_harness_tools.py`, an SDK-independent module in the `_tools`/`_meta_tools` style.
- Define `HarnessFloorPayload` and `ActivePersonaDocument` pydantic v2 strict-frozen models carrying the concatenated operator rules and the resolved active-persona document.
- Add `build_harness_floor_payload(persona=...)` reading `operator_rules_text()` verbatim plus the active persona document, resolved through the `aeat.agent` package facade (`iter_personas`, `operator_rules_text`) only.
- Add `render_harness_floor_text()` embedding both texts verbatim under headings so a tools-only client that reads only the text block still receives the whole operating layer.
- Add `build_harness_floor_tool()` lazily adapting to the SDK `Tool`, annotated `readOnlyHint`/`idempotentHint`, taking no arguments; the tool name `aeat_harness_load` follows the per-verb `aeat_<key>` naming convention.

## Outcome

Floor tool module complete and standalone-importable: the universal ADR R4 floor channel is now buildable, ready to wire into the server in S11. `build_harness_floor_payload(persona=None)` returns the rules with no active persona; with a persona it returns that persona's shipped document verbatim. Ruff, ruff-format, and pyright clean. Server wiring and tests follow in S11 and S12.

## Notes

Named the tool `aeat_harness_load` (not a literal `harness.load` dotted token) so it is a valid MCP tool identifier consistent with the existing per-verb naming convention; the ADR's conceptual `harness.load` maps onto it exactly as `tool_name_for_command` would. The floor is always advertised regardless of persona (wired in S11) - the floor must never be scoped away.
