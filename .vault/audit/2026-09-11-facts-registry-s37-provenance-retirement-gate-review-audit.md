---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:00b2ebe65a97faa9efab8e3c68c10a74096aba40b83534876f7d1fe15ff87492'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S37 provenance retirement gate review`

## Scope

Read-only re-review of the S37 remediation against W04.P18.S37, the facts provider registry, real fact resolver, active plan, and S80/S85 retirement ledger.

## Findings

### projection-provider-omitted-from-live-result-denominator | medium | Resolved: registered modelo projections are included in the live resolver denominator

When a registered projection provider exists, the live gate now loads actual modelos and obtains the full governed catalogue through `compile_registered_fact_providers` with those modelos. The real resolver therefore receives authored and projected results under the same provenance check. The focused mutation proves the loaded modelo tuple reaches the compilation seam; the existing malformed-result mutation still proves an applicable result stripped of all evidence fails.

### completed-hold-removal-is-misclassified-as-stale | medium | Resolved: holds are required while open and forbidden after closure

Each named S80 row and the S85 lane is now required only while its owning plan step remains open. Once that step closes, a retained row or lane is stale while its removal is accepted. The focused mutation covers closing and removing both the S81 catalogue row and S85 grounding lane. The separately classified technical `country_names.toml` vocabulary remains required and cannot be admitted as a temporary hold.

## Recommendations

Final verdict: CLEAR. Keep provenance evaluation on the complete registered fact catalogue, including modelo projections, and keep temporary retirement entries state-dependent on their exact open plan steps. Future projected providers or approved temporary holds require an explicit mapping and mutation coverage.
