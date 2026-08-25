---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f7622d2a4b2e387a0191d1598d4c873f0f0621ad1d25dc085b20f2f2427e0cd0'
step_id: 'S115'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# classify the S112/S113 structural-helper handoff in the frozen census selector

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/application/registry/source_connectivity.py`
- `dev/source_connectivity/discovery.py`
- `dev/source_connectivity/tests/test_census_completeness.py`
- `dev/source_connectivity/tests/test_m232_deferral.py`
- `.vault/audit/2026-08-25-source-casilla-integration-s115-related-party-locator-followup-audit.md`
- `.vault/exec/2026-08-22-source-casilla-integration/2026-08-22-source-casilla-integration-W06-P20-S115.md`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md`
- `.vault/index/source-casilla-integration.index.md`

## Description

- Apply S113's reviewed `not_applicable` classification only to
  `revision_selection_coordinates` and `portal_integrity_error` through the
  existing `remaining_calculation_helpers` selector.
- Freeze that selector at 267 live helpers and the independently recorded
  `sha256:3b827ccf9f7fd2c3b30a37f042e9ede32be236d0b4600c8e3a09dcebbfeeeb6a`
  digest. The digest remains the canonical identity proof; the count is a
  secondary drift guard.
- Add no capability IDs or candidate rows, and do not change any other census
  disposition, owner, follow-up, or registry destination.
- Correct only the mutation-backed inventory helper/projection source
  locators. Retain the service anchor at `413` because it still anchors the
  existing closing-authority persistence evidence.
- Correct the related-party capability and grounding locators from the adjacent
  withholding branch to the live `per_related_party_operation` dispatch, with a
  mutation gate; retain all row disposition and deferral governance.

## Outcome

The two S112-discovered identities are frozen as structural
`not_applicable` selector members, not as source-connectivity candidates. The
selector rises from 265 to 267 helpers under its exact updated digest, and its
new optional count cannot replace or relax digest validation.

The inventory row keeps its established encrypted owner, candidate status,
and dispositions; only its stale function-line locators now point to the live
definitions. No source, binding, resolver, lifecycle, export, or census-owned
fact was introduced.

The related-party row keeps its established ingress-blocked governance. Its
two locator references now name the actual RELATED_PARTY dispatch and the
focused mutation gate refuses the prior adjacent line.

## Notes

- The S113 independent review at `f143fc2ef5` accepted the two-helper
  classification. S112 had recorded the 265-to-267 drift and exact digest.
- This is evidence-backed selector maintenance, not adjudication of a new
  candidate. Unrelated source-scope mutation-test failures remain outside this
  step.
