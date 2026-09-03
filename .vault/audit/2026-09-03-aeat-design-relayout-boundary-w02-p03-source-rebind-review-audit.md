---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e306fcace15b82805fb0fbaf803dce2ac806a7f6e8a300b95f77c2480695574c'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# `modelo-200-semantic-crosswalk` audit: `W02.P03 source-rebind review`

## Scope

Independent review of W02.P03 S05 and S06: the source-rebind planner, its
mutation surface, and focused detector tests. The review checked target-map
ownership, source identity, byte preservation, refusal coverage, isolation,
and publication safety.

## Findings

### source-rebind-transaction | high | A multi-file apply can publish a partial rebind

`apply_m200_source_rebind_plan` completes preflight before writing, but then
calls the one-file atomic writer in a loop over 965 paths. An I/O failure after
one replacement leaves the canonical registry partly rebound, with no journal,
rollback tree, recovery protocol, or failure-injection test. The next run
detects partial application, but cannot restore the original declaration
sources. This violates the phase's atomic mutation requirement.

## Recommendations

Implement a transactional staged-tree or per-file rollback protocol with a
durable journal, then test a deliberately interrupted cutover to prove that
the canonical tree is either wholly unchanged or wholly rebound.
