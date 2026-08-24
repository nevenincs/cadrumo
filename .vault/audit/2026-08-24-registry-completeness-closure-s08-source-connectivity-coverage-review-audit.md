---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6a33c0a45c30be40d677f88fbe61290bbb75ccbf02422d3ba35974620504a884'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S08 source-connectivity coverage review`

## Scope

Independent review of `47125a8889` for S08's source-connectivity composer,
its application-registry facade and API reference, the source-census authority
contract, and focused tests. The review exercised census rows against the live
validated registry, checked every terminal, candidate, blocked, expired, and
unmeasured branch, and inspected the source proof boundary.

Focused Ruff passed. The focused pytest run was timeboxed before it completed
in the shared worktree. `git diff --check` reports one CR-only trailing
whitespace byte in the generated API toctree entry; it has no API or contract
effect and is not an audit finding.

## Findings

### connected-proof-not-revalidated | high | A once-valid connected claim can remain a release pass after live proof loss

`compose_source_connectivity_coverage` accepts an already-built
`SourceConnectivityCensusManifest` and never receives or invokes the live
`SourceConnectivityProofAuthority`. A `connected` row is therefore accepted as
terminal solely because it was validated at an earlier parse boundary. A later
loss of source enrollment, operator reachability, encrypted-revision identity,
or executable-evidence digest still yields a satisfied limb. This contradicts
the accepted closure predicate's requirement for current evidence and lets a
stale production path support a release claim.

### terminal-expiry-treated-as-success | high | Expired terminal evidence is exempted from stale-evidence refusal

The composer explicitly filters terminal dispositions out of its expiry check.
The census schema permits a terminal `not_applicable`, `duplicate_or_stale`,
`manual_by_design`, or `connected` row to carry an `expires_on` date. A
controlled schema-valid terminal mutation with an expiry in 2020 produced
`satisfied` for Modelo 100 revisions 2020 through 2025 at an as-of date in
2026. Expiry must turn every applicable disposition into a visible
stale-evidence refusal, not grant a permanent pass.

### model-wide-destinations-overclaim-revision-scope | high | Model and role/source matching lets one scoped decision satisfy other revisions

`RegistryDestinationCandidate` has no revision, filing-year, or period
coordinate, and `_candidate_applies_to_revision` matches only modelo plus a
semantic role or binding-source kind. The live census describes
`inventory.stock-valuation` as a 2025 prerequisite, yet its three roles match
Modelo 100 revisions 2020, 2021, 2022, 2023, 2024, and 2025. Likewise, the
Modelo 193 row grounded at the 2025-y-siguientes binding matches both its 2024
and 2025-y-siguientes revisions. When either row is made terminal, the composer
can satisfy each unadjudicated revision. That is scope-inadequate evidence,
not an exact per-revision source mapping.

## Recommendations

- Complete `W01.P02.S45`: revalidate every connected claim through the live
  proof authority during composition and prove proof loss or digest mismatch
  refuses the limb.
- Complete `W01.P02.S46`: make expiry apply to every applicable census
  disposition and add mutation-bite coverage for expired terminal evidence.
- Complete `W01.P02.S47`: add exact revision, filing-year, and period scope to
  census destinations, then prove the Modelo 100 and 193 decisions cannot
  cross-satisfy other revisions.

