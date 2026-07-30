---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S294'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Land the proven MCP identity seeding fix once the wizard results module is committed, so both transports report the same schema count and the parity assertion is no longer comparing two equally blind sets

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`
- `src/cadrumo/entrypoints/mcp/_harness_tools.py`
- `src/cadrumo/application/wizard/_compiler.py`

## Description

Land the proven identity fix once its blockers cleared, and confirm it owes the
unsanctioned-import ratchet nothing.

## Outcome

SATISFIED. Landed at `0918c3f7a7`.

Both blockers dissolved rather than being negotiated away. The transport
divergence ended when a peer bridged the schema-name filter; the parity suite
passes 8 of 8 at the landing HEAD. The ratchet blocker ended by better
engineering: the held version reached the seeding authority through two
deferred function-local imports, which would have moved the ratchet and
required an allowlist entry plus a ceiling raise, and that was authorised. The
landed version imports at module level in both call sites instead.

Confirmed by inspecting the commit rather than trusting the instruction: it adds
zero function-local imports and removes none, so it contributed nothing to the
domain cycle-break count and correctly touched no ceiling.

The ratchet's residual red - 52 live sites against a ceiling of 50, and two
ceilings carrying slack - is therefore entirely peer drift with nothing
attributable to this campaign.

## Notes
