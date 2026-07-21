---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S426'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Derive MCP guided-prompt period completions and descriptions from the canonical RegistryPeriodCode vocabulary, removing the invalid ANUAL alias and pinning client-visible parity

## Scope

- `src/aeat/entrypoints/mcp/_completions.py`
- `src/aeat/entrypoints/mcp/_prompts.py`
- `src/aeat/entrypoints/mcp/tests/test_prompts.py`

## Description

- Ground the prompt and completion surfaces with `vaultspec-rag`, then read the MCP completion, prompt catalogue, real server wiring, integration tests, and the core period vocabulary in full.
- Replace the MCP-local period tuple, including its invalid `ANUAL` alias, with the string-normalized finite `accepted_period_codes()` core contract.
- Derive the guided-prompt period description from `accepted_period_patterns()` so the finite standard, exterior, and ad-hoc forms remain accurate and `EVENT-N` is described as an open event-driven pattern rather than offered as a fabricated completion.
- Extend the public catalogue assertion and invoke the real MCP `prompts/list` and `completion/complete` handlers to prove their client-visible description and candidates agree with the core authority.

## Outcome

Guided MCP workflows now advertise the same finite period-code vocabulary accepted by core, including annual `0A` rather than invalid `ANUAL`. Completion candidates are always strings even where the core’s closed standard values are `StrEnum` members. The prompt description preserves the open `EVENT-N where N is an integer` grammar without claiming it belongs to a closed candidate list. No fake, mock, stub, patch, or monkeypatch was used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/mcp/_completions.py src/aeat/entrypoints/mcp/_prompts.py src/aeat/entrypoints/mcp/tests/test_prompts.py`
- `uv run --no-sync pytest src/aeat/entrypoints/mcp/tests/test_prompts.py -m integration -q` — 10 passed.
- Independent code review approved the core-derived finite completion and open-pattern description contract, and reproduced both focused gates.

## Notes

The project’s default pytest selection is `-m unit`; this integration-marked MCP file correctly collects no tests under the default selection, so validation explicitly selects `-m integration`. The S426 plan checkbox is intentionally unchanged pending independent review.
