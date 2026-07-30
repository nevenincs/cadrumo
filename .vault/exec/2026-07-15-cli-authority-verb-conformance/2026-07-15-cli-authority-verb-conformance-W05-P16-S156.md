---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S156'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert MCP risk annotations match the operator risk table

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_risk_table_parity.py`

## Description

- Run the MCP risk-parity gate and confirm the annotations match the operator risk table.

## Outcome

The named gate passes. It holds the MCP risk annotations in parity with the operator risk table, so the destructive and handoff classifications verified on the risk table cannot be contradicted by what the MCP surface advertises to an agent. This matters because the agent-facing annotation is what elicits human confirmation before a destructive call.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
