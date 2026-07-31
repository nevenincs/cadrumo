---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:685e089234cfa8081f8780a44ce73f09ec4300228ac0e889d9e9c1e4d6f03eaf'
step_id: 'S09'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 00349c998) - wire the persona-scope filter into the MCP PreToolUse dispatch path so the declared boundary actually gates the tool call, closing the critical dead-code finding

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Add `active_persona()` reading `AEAT_MCP_PERSONA` in `_server.py`.
- Filter `_list_tools` to the active persona's declared families.
- Refuse an out-of-scope `_call_tool` invocation before the
  confirmation gate runs, so the persona-scope filter declared in
  `P05.S08` actually gates the live request path instead of sitting
  unwired.
- Document and pin the family-granularity limitation of the current
  filter.

## Outcome

Landed in commit `00349c998`. Closes the CRITICAL
`d1-dead-code-now-resolved` finding recorded in
`2026-07-02-agent-harness-content-review-audit`: the mechanism declared
in `P05.S08` type-checked and unit-tested in isolation but had no live
call site until this Step. 41 MCP tests green at landing.

## Notes

Bundles a minor peer type-ignore comment in `_server.py`, noted in the
landing commit message; no functional overlap with this Step's scope.
