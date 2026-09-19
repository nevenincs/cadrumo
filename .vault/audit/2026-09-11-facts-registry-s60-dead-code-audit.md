---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8ffd80d019c78ea0e48bca4d0d0e8679cdbcd3c4476d398032bfc37a2d60c309'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `s60 dead code`

## Scope

Audit the approved W04.P19.S60 facts-registry retirement scope with the project dead-code and shipped-module reachability tools. Determine whether an exact legacy provider, adapter, raw parser, or campaign-owned test is demonstrably orphaned and safe to delete.

## Findings

### s60-dead-code | low | General reachability backlog is not an authorized facts-registry deletion list

The dead-code audit is clean for 5,167 modules. The unreachable-code audit reports 17 shipped modules and 481 symbols, but no orphaned tests. The only campaign-adjacent entries are signed-authority IVA projections and a compiler catalogue boundary still needed to ground the explicitly retained IVA legal tables. The retirement gate confirms the retired compiler providers, rate repository, and raw treaty directory are absent. The remaining IVA grounding surface is live and is an explicit S80/S85 hold. No exact campaign-owned orphan has been established.

## Recommendations

Close S60 without a deletion checkpoint. Triage the broad reachability output independently, retaining every IVA projection and grounding surface until S81 through S85 have established the typed replacement and equivalent evidence refusal.
