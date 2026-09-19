---
tags:
  - '#audit'
  - '#binding-resolver-contract-unification'
date: '2026-07-04'
modified: '2026-08-26'
body_hash: 'sha256:3c484ac456e4dc230ec1b1da33d18ff376e034f972cc16af2e14a98db899b485'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# `binding-resolver-contract-unification` audit: `S12/S14/S18 evidence review`

## Scope

Review of the resolver-contract follow-up evidence records for S12, S14, and S18. The review checked that S12 and S18 are recorded as blockers rather than implementation closure, and that the S14 aggregate CLI evidence remains a narrow command-boundary confirmation.

## Findings

No blocking findings in the evidence records.

The single code change updates the boundary gate's canonical aggregate CLI path from
`_modelo.py` to `_modelo_aggregate_cli.py`, matching the current command registration
split. The test still scans all non-test CLI modules for duplicate `aggregate_per_modelo`
usage outside that one module and still rejects direct family-specific aggregation calls
everywhere, including the canonical module. Focused tests and the feature vault check
passed before this review.

The S12 blocker record is accurate under the current architecture: `foreign_asset`
is explicitly re-ratified as deferred by the source-kind deferrals ADR, and S20/S21
remain blocked by the M720 row-indexed envelope and M347 counterpart-source modelling
gaps. Enrolling the resolvers or removing `FOREIGN_ASSET` from the deferred set now
would overclaim and contradict the freeze.

The S18 blocker record is also accurate: the final full-surface resolver-contract
gate is downstream of P03, so running or checking it while S20/S21/S12 remain blocked
would make the plan appear complete before the resolver/envelope decisions exist.

## Recommendations

Leave S12 and S18 unchecked until the named P03 blockers are resolved or replaced by a coordinator-approved successor decision. S14's plan-file blocker has cleared; current focused re-verification still proves the aggregate command is a thin CLI projection. The broader aggregation service suite is red only because unrelated non-authored Modelo 145 registry scaffolding invalidates registry authority before the aggregation assertions run, so it is recorded as gate-health inventory rather than an S14 implementation blocker.
