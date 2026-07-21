---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add tests for the floor tool and resource templates

## Scope

- `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`

## Description

- Add `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`, real-behavior tests over the floor tool and resource surface plus the wired server.
- Assert the floor payload returns the shipped operator rules verbatim (and no persona when un-personified), and carries the active persona document verbatim when personified.
- Assert the rendered floor text embeds both the rules and the active persona.
- Assert the resource surface enumerates exactly the shipped skills, rules, and personas; every advertised URI resolves as `text/markdown`; a skill, a rule, and a persona resolve verbatim; the three templates declare the three kinds; and malformed/unknown URIs refuse cleanly.
- Drive the real built `Server` (persona=verifier): the floor tool is in `tools/list`, `resources/list` and `resources/templates/list` match the SDK-independent sets, `resources/read` returns the persona verbatim as markdown, the floor `tools/call` returns the active-persona payload, and prompts/resources capabilities are negotiated.
- Gate the SDK-dependent tests on `find_spec("mcp")`: assert a graceful `ModuleNotFoundError` when the extra is absent, never a skip.

## Outcome

14 tests, all green; ruff and pyright clean. The full W02 phase-end gate `pytest src/aeat/entrypoints/mcp src/aeat/agent` is green (166 passed) and the rule-surface drift gate is green (6 passed).

## Notes

Step-closure was held open across the session because a peer's uncommitted deletion of `TransactionParticipationIndexRepository` in `domain/modelos/_participation_index.py` broke the shared CLI import chain that `build_tool_descriptors()` transits, reddening the 3 server-driven tests here (and the whole cross-package gate) via `ImportError` — an owner-triaged peer break, not this surface (reported to team-lead; not touched per uncommitted-wip-is-not-orphaned). The 11 SDK-independent tests passed throughout; all 14 passed before the peer deletion landed and again after the peer relocation restored the symbol. Closed once the import chain was green and the full W02 gate passed 166.
