---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:283ef5aab9bc27a7f4d1c4cbc874bf2471803b652ca2ab66a46042b57e623daf'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `S15 MCP action projection`

## Scope

Independent fresh-context review of `W02.P04.S15`: the MCP projection of the
canonical application action catalogue through the shared operator-surface
resolver. Reviewed the current shared diff and `HEAD` against the accepted ADR,
research, reference, plan, S14 execution record, live Click/result-schema joins,
SDK adaptation, and the action/output-schema tests. Verified that the projection
keeps application applicability out of MCP, groups immutable capabilities by
target key in deterministic action-id order, and derives the Notice and error
schemas from their canonical models.

## Findings

### input-schema-identity | medium | Closed: a mapping-key/schema-key mismatch could cross-wire a resolved action

The initial review demonstrated that supplying the real `overview.status`
`VerbInputSchema` under the `config.profile.create` mapping key produced a
profile-create capability with the overview Click path and no required inputs.
That violated the exact result/input/Click identity join. The current
`resolve_mcp_action_capabilities` implementation rejects the mismatch before it
constructs reconciliation rows, and the direct real-schema regression at
`src/cadrumo/entrypoints/mcp/tests/test_action_projection.py:99` proves the
failure path. Re-run verification passed.

### tools-list-wire-evidence | low | Closed: direct SDK adaptation alone did not prove the advertised session surface

The original projection test stopped at `build_sdk_tools`, while the actual
MCP `tools/list` response is assembled by the server callback. The narrowly
additive real in-memory-session regression at
`src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py:105` now traverses
initialization and `session.list_tools()` and proves the resolver-backed
`x-cadrumo-action-capabilities` extension for `overview.status` survives the
default core surface. This also independently confirms the live SDK boundary
rather than only the descriptor object.

No open findings remain in the reviewed S15 surface. The resolver is the sole
authority for action-to-live-schema resolution; MCP contributes only inventory
rows and an immutable target-key projection. Distinct action IDs sharing a
target retain a deterministic tuple, and duplicate, mismatched, orphan,
ambiguous, and insufficient-source inputs fail closed. The shared output
schema now derives its Notice and ErrorEnvelope definitions from the canonical
models, exposes `action`, and contains no `suggestion` compatibility field.

## Recommendations

No further code change is recommended. Retain the two closed regressions: the
mapping/schema identity refusal protects the resolver join, and the initialized
MCP-session proof protects the on-wire `tools/list` extension. Focused
verification after the fixes: 12 integration tests passed across the action
projection and client-handshake modules; Ruff passed on the five S15 surfaces;
and BasedPyright reported zero errors, warnings, and notes. An additional
direct real-session probe using explicit `SurfaceMode.FULL` observed
`operator.profile.create` on the advertised `config.profile.create` tool;
the default-core on-wire proof is instead the `overview.status` regression
recorded above.
