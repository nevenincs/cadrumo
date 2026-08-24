---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6b22c4cc18226d878b08db5a71ea714b77ab40951ea26bd7668c1e2ca23d8036'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-operation-observation-research]]"
  - "[[2026-08-24-tui-operation-observation-adr]]"
---
# `tui-architecture` audit: `s121 current only purge`

## Scope

Audited the PRE_RELEASE operation persistence cutover against the canonical plan and current-only ADR. Reviewed the lease and journal readers, acquisition path, parser wiring, migration fixtures, refusal tests, exact symbol census, and focused/full operation test results.

## Findings

### current-only-cutover | low | No S121 safety defects found

The v1 lease model, retired operation-keyed path helper, acquisition migration method and call, and the private journal parser wrapper are deleted. The remaining canonical readers hydrate only lease schema v2 and persisted snapshot schema v6. Superseded lease and journal markers are refused with durable bytes unchanged. No production operation compatibility reader, migrator, or legacy fixture remains in the scoped packages.

The focused S121 tests passed (11 tests) and Ruff passed. The complete operation application/persistence lanes passed 301 tests; their one failure is an unrelated concurrent persistence-facade export assertion caused by another worker's secure-reference export change, outside S121.

## Recommendations

No S121 code changes remain. Resolve the concurrent facade baseline independently before using the aggregate operation lane as a global green signal.
