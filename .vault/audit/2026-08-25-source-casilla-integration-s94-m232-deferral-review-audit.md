---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:256b915eef421f63f69090b7bfcda0f6e19caa18eef6364ed9c52f5070c409e7'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S94 M232 terminal deferral review`

## Scope

Independent review of the M232 terminal-deferral proof, its governing S92/S93 evidence, the calculation route, diagnostics, census coverage, connected-proof composition, export layout, direct M232 row replay, and the focused advisory gate.

## Findings

### deferred-advisory-coverage | low | corrected for every registry-declared deferred kind

The advisory parametrisation omitted `gasto193_contributor` even though live Modelo 193 revisions declare it and the real diagnostic boundary emits `unhandled_binding_source`. The correction adds the 2025-y-siguientes revision and derives the completeness set from live registry declarations. `withholding296` remains deferred but has no live binding declaration, as its census row is `registry_blocked`; there is no calculate boundary from which an advisory could truthfully be asserted.

### m232-negative-proof-scope | low | corrected to preserve direct positional replay

The deferred `related_party_operation` source has no calculation-route owner, connected encrypted-proof fixture, or repeated-record projection endpoint, and the census closure limb remains refused. This does not negate the distinct direct positional `Modelo232VinculadaRow` detail-row path, which persists and replays fixed M232 casillas; the S94 execution record now states that boundary explicitly.

## Recommendations

Keep `related_party_operation` ingress-blocked until the S93 source-owner predicate is met. Add a `withholding296` advisory case only if a validated revision first declares a binding with that source; the registry-derived completeness gate will require it then.
