---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:f13df3f8f796121c0f401605fa4b3bc327d56bb0b99eec709a0a318f50573429'
step_id: 'S277'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Seed the profile-key registry on the MCP path itself rather than relying on a wizard import side effect, and prove whoami through a real stdio subprocess client

## Scope

- `src/cadrumo/entrypoints/mcp/`

## Description

Seed the profile-key registry from an initialisation point the MCP entrypoints
actually execute, rather than relying on a wizard import side effect.

Prove the fix against a real server process, not a passing in-process test.

## Outcome

SATISFIED. Landed at `0918c3f7a7`, four files.

The registry had exactly two seeding points, both test conftests, neither
reachable from the MCP or CLI-config trees, and every production wizard import
is function-local under the lazy-import policy. So nothing seeded it in a
shipped process. The fix promotes the CLI's existing private helper to a
documented idempotent public symbol and calls it at the server's initialisation
point and inside the identity reader itself - one authority, two call sites,
not a second mechanism.

Acceptance evidence, to the standard set before the work began: a real
`cadrumo-mcp` stdio subprocess spawned outside pytest returned
`isError=False` for both `cadrumo_whoami` and `cadrumo_harness_load`, with a
rendered identity payload. The clean-interpreter probe that originally proved
the defect inverted: the wizard stays absent and the read returns keys instead
of raising. Twelve of the twelve identity failures pass.

A third conftest import would have turned all twelve green and left the shipped
server broken. That trap was named in advance and avoided.

## Notes
