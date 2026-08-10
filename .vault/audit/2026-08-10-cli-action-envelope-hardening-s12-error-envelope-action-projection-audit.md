---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:23d43431487fc8da672ed449438a78193945f4f466979a8dacedc43be50cdd15'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---
# `cli-action-envelope-hardening` audit: `S12 error envelope action projection review`

## Scope

Independent review of `W02.P04.S12`: the strict `ErrorEnvelope` action
projection, lazy public-schema completion across the core import boundary,
error JSON validation and rendering, the modelo bad-parameter reader, and MCP
transport construction. The review checked the accepted contract that
`ResolvedPreconditionAction` is the sole error action channel, while
`default_suggestion` and exception `suggestion` values remain inert migration
inputs for later Steps.

Reproduced verification: the focused error-envelope and JSON round-trip suite
passed 30 tests; the MCP runtime integration suite passed 20 tests; the
seven-file Ruff and BasedPyright gates passed with no diagnostics; and the
scoped diff has no whitespace errors.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW S12-specific finding. The public facade
completes the exact Pydantic model without restoring the retired field; core
JSON and MCP validate the same strict model; text and the bad-parameter reader
no longer promote registry or exception prose to executable authority; and the
added tests prove typed action serialization, retired-field rejection, and
default/override inertness.

## Recommendations

No S12 implementation change is recommended. Preserve the explicit later-step
ownership of the remaining registry rows and legacy assertions: do not add a
compatibility `suggestion` field or helper while resolving the S28 and S50-S57
migration debt.

The broader core-error suite remains red only on the peer-added
`REFUSED_M303_CARRY_INGRESS` reachability adjudication (`52 passed, 1 failed`)
in `test_suggestionless_reachability`; it is outside this transport-projection
Step and needs its owning decision rather than an S12 workaround.
