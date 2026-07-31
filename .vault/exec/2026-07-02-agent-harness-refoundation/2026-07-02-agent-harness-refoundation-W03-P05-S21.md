---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:1ff6a5799123db109376e9652f7ab5e7e20e652791711a116a5e6423601c4e40'
step_id: 'S21'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add tests for elicitation enforcement and the degradation matrix

## Scope

- `src/aeat/entrypoints/mcp/tests/test_elicitation.py`

## Description

- Add `test_elicitation.py` covering the degradation matrix: BLOCK refuses for any client, AUTO passes, CONFIRM+elicitation elicits, CONFIRM+no-elicitation refuses a handoff verb (no channel) and hints on a non-handoff verb.
- Cover the fail-closed decision mapping: accept+true proceeds; accept+false, missing field, no content, and a non-boolean-true value all refuse-not-confirmed; decline and cancel refuse; an unknown action fails closed to a decline.
- Assert the request payload is exactly one boolean confirm field (no argument values or figures) and interpolates the command, and that the handoff and local consequence messages differ.
- Assert the two refusal messages interpolate the command.

## Outcome

Eight real-behavior tests pass over `_elicitation.py`. The matrix, the fail-closed decisions, and the argument-free localized payload are all covered. Because user-facing strings flow through `tr()` in the default (Spanish) locale, the assertions check command interpolation and payload structure rather than hardcoded prose, so they stay green across locale changes. Ruff check/format clean.

## Notes

The request-payload test is the concrete guard for the MCP-spec constraint that elicitation must never request sensitive information: it asserts the requested schema carries only the `confirm` boolean and no argument-bearing fields, so a future change that tried to thread a figure into the elicitation form would fail here.
