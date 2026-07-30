---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S02'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Extend the destination guard into one all-destination version-identity authority checking the three PyPI projects, the v-tag and release namespace including drafts, the monotonic manifest floor, and the burned ledger, refusing with the owning destination named, gate: uv run --no-sync pytest dev/release/tests -q -k version_identity passes with one refusal case exercised per destination class plus the burned-version and floor refusals

## Scope

- `dev/release/promote_python_cohort.py`
- `dev/release/version_identity.py`
- `dev/release/tests/test_promote_python_cohort.py`

## Description

- Search the tree for any existing all-destination version-ownership authority.
- Add the identity module with a pure decision core and a thin network shell.
- Add the operator CLI with an offline mode for seal-time pre-flight.
- Add the test module and prove it non-vacuous by mutation.

## Outcome

Landed under the commit subject `feat(release): ask every destination whether it
owns the version, not just the index`.

Four independently sufficient conflicts: any of the three package indexes; the
tag and release namespaces, drafts included because a draft holds its tag; the
monotonic manifest floor; and the burned-version ledger. Every conflict is
reported rather than the first, so an operator fixing one collision does not
re-run to discover the next, and a burn refusal quotes the recorded reason
rather than sending the reader elsewhere.

The decision core is pure. Observed state goes in and refusals come out, so
every rule is proven against real data with no test double standing in for a
destination, and network access stays confined to the shell that gathers state.
A non-404 network failure refuses rather than reading as absence: an unreachable
index cannot prove a version is available, and reading an error as a clean
result is how a guard silently permits the collision it exists to catch.

Gate: eighteen tests, one refusal case per destination class plus the permit
case, since a guard that refuses everything proves no more than one that refuses
nothing.

Anti-tautology proof: deleting the tag-namespace rule, which is the exact
historical blind spot, turns three tests red; restoring returns eighteen green.

## Notes

A test defect was caught by its own gate during authoring. The all-conflicts
case asserted six refusals where the correct count is seven, an arithmetic slip
in the test rather than a fault in the module. The expectation was corrected and
a per-class assertion added, because a bare count would let a whole conflict
category be dropped without any test noticing.

Discovery substitution as recorded for the preceding Step: the semantic
discovery service was unusable, so discovery was performed manually and
exhaustively. No all-destination ownership authority existed; the only
version-ownership code asked one index over the network and raised on conflict.
