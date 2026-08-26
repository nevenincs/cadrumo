---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
step_id: 'S29'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Remove the dead mutable fingerprint-TTL bindings and caller-less wrapper

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`
- `src/cadrumo/domain/calculations/registry/loader_cache.py`
- `src/cadrumo/domain/calculations/registry/loader_fingerprints.py`

## Description

Mutable registry roots are already unconditionally uncached; only bundled roots use the fingerprint cache. The mutable TTL constant, its keyword plumbing, and a forwarding wrapper therefore carried no behaviour and falsely suggested a second cache policy.

## Outcome

Reachable commit `18a5d6b5de` contains the exact deletion: the mutable TTL constant, all three bindings, and the caller-less loader wrapper are absent, with no compatibility replacement. A repository sweep returns zero occurrences of the retired symbols.

The mutable-tree invalidation and fingerprint-content collision gates passed 4/4. Ruff format/check and `git diff --check` passed. The cache-isolation module produced 10 passes and one bundled-root cross-session failure because the actively edited shared registry changed fingerprint between child sessions and correctly created a second keyed pickle; that failure does not exercise the deleted mutable plumbing.

## Notes

The accepted 2026-07-07 registry disk-cache ADR still describes a mutable TTL constant. Its root-classification decision remains valid, but amending accepted ADR prose requires explicit operator approval and was not folded into this code row. No Modelo 200 path was touched.
