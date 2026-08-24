---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e715f86b355258bcfe59b1126f190837189f544f390407c31fc93c00171196dc'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-W02-P19-S120]]"
---
# `tui-architecture` audit: `s120 projection services review`

## Scope

Reviewed `W02.P19.S120` against the accepted operation-architecture decision, its rejected staging provenance and research, the canonical plan row, its execution record, the registry/facade bindings, and the focused real-adapter tests. The review covered single-home authority, exact identity and terminal validation, separate response authority, secret/error/reference non-leakage, current-only behavior, and control-path races.

## Findings

### s120-projection-services-review | high | Resolved during review: cancellation now preserves expected-revision semantics

The original service compared `expected_revision` before invoking an ID-only supervisor method, allowing a transition between the comparison and mutation. The current control port carries the expected revision into the supervisor; a changed snapshot is rejected before mutation, and a later compare-and-swap failure is re-read and returned as `stale_operation_revision`. The focused real-journal proof confirms the stale supervisor call leaves the durable record byte-identical after the winning transition.

### s120-projection-services-review | medium | Resolved during review: projection contracts now have real composition and durable-reader coverage

Output-validation cases now compose registries normally instead of bypassing registry validation, and refresh resolution uses a new filesystem-backed reader after persistence. The focused suite covers REVIEW unsupported-version, unknown-operation, and not-pending refusals, refresh unsupported-version, non-terminal, and adapter-unavailable refusals, exact digest/schema/expiry/output checks, separate bearer closure and token-buffer zeroization, plus the caller-result-reference exclusion. No mock, patch, skip, xfail, forged binding, duplicate resolver, or compatibility shim was found in the S120 surface.

## Recommendations

- Preserve the expected-revision supervisor port and its real-journal stale-mutation proof.
- The existing `W02.P19.S123` C0 conformance work should retain ownership of the exhaustive endpoint-refusal and response-bearer matrix across the complete public contract set.

Final disposition: approved. No open critical, high, medium, or low findings remain within `W02.P19.S120`.
