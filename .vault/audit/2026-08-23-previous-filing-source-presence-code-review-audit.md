---
tags:
  - '#audit'
  - '#previous-filing-source-presence'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:93bdf3cb979f14a13b5bb42cf443bc7bb5d8e12b9f09c84e90ea381b36ad2107'
related:
  - "[[2026-08-23-previous-filing-source-presence-reference]]"
---

# `previous-filing-source-presence` audit: `Canonical previous-filing source presence code review`

## Scope

Reviewed the canonical previous-filing selector, registry declarations, typed
requirement projections, resolver, live declaration capture, cross-period
clean-state gate, and focused tests after issue 113 exposed a false all-casilla
completeness requirement.

## Findings

### stale-all-four-test | high | fixed obsolete M100 completeness assertion

`src/cadrumo/domain/calculations/registry/tests/test_formula_runtime_previous_filing.py:178`
still expected the committed M130 annual binding to reject a filing containing
one applicable M100 source. It was replaced with the canonical `y/o` behavior.

### clean-state-presence | high | fixed empty-required subset could look clean

The initial implementation checked only the mandatory subset. An empty subset
could therefore pass clean-state with none of the candidate casillas. The gate
now consumes the shared `source_presence_gaps` primitive and requires every
registry-derived any-of group to intersect the observation.

### coalesced-binding-policy | medium | fixed per-binding any-of groups retained

Coalescing requirements by source filing originally unioned candidates and
could lose each binding's independent any-of condition. Typed
`source_presence_groups` now preserves each registry binding's condition, with
a focused two-binding disjoint-group regression.

### canonicality | low | passed no fixture or Python policy mirror remains

The M100 schema remains unchanged and canonical. Parser fixtures remain sample
documents. The aggregation-op/tuple-position `_optional_source_casilla_ids`
helper was deleted; both affected presence policies are declared in M130 TOML.

## Recommendations

No open implementation finding remains. Focused Ruff passed. Resolver,
registry, M130, continuity, and absence-versus-malformed tests passed in the
selected lane (51 tests), followed by 40 focused previous-filing tests and the
initial requirement-projection checks. The stricter disjoint-group regression
was then authored, but its final rerun was prevented by concurrent unrelated
shared-worktree changes that temporarily removed
`BindingAggregationOp` from the core facade while another modified module still
imports it; that external failure was not absorbed into this feature.
