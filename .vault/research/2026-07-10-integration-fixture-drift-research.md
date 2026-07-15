---
tags:
  - '#research'
  - '#integration-fixture-drift'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-08-integration-fixture-drift-plan]]"
  - "[[2026-07-08-integration-fixture-drift-audit]]"
  - '[[2026-07-10-integration-fixture-drift-adr]]'
---
# integration-fixture-drift research: retrospective closeout grounding

## Question

How should the completed integration-fixture-drift campaign be represented when tests lagged changed contracts and the feature inherited the earlier no-ADR execution context?

## Findings

Fixture drift is a test contract that no longer matches valid application behavior after a contract change. The completed work aligned test identifiers, required identity inputs, bucket-session setup, and long-tail expectations with the live contracts.

Fixture repair is distinct from an architectural or product-behaviour decision. Where triage reached such a question, the evidence must remain tied to prior governing authority or an explicit operator ruling; this campaign must not be treated as a blanket source of new authority.

The completed plan and close evidence establish a bounded remediation outcome. Parallel flakes, peer-owned failures, and unresolved work remain outside that outcome.

## Recommendation

Create a feature-specific retrospective closeout ADR. It should record the campaign evidence and scope, preserve the historical absence of a feature ADR, and avoid manufacturing authority for product or architectural choices. Put all evidence and authority relationships in frontmatter metadata.
