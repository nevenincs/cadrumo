---
tags:
  - '#audit'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1b739a14dc4aa7caaf257fa86e2351e3d993d9c47f52833c0237c580c82e25f0'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-suite-red-at-head` audit: post-archive ownership correction

## Scope

This post-archive curation audit corrects the ownership language in the archived
tracker reconciliation. It does not alter the historical tracker, revive its
retired umbrella rows, or claim that the registry is green.

The audit re-ran the exact claimed-year consistency gate on the current tree,
the canonical application registry verifier, and the cross-authority closure
predicate. VaultSpec RAG discovery was used before adjudication to find the
active plans already carrying the same work and prevent redeclaration.

## Findings

### tracker-ownership | high | Archived umbrella rows are not current owners

The archived reconciliation incorrectly continued to describe retired
`P03.S22` and `P03.S23` as owners. Those rows were non-executable
close-the-world umbrellas and remain retired. Archival means the historical
tracker was reconciled and superseded; it never means the registry or its
release predicate is green.

### claimed-year-gate | high | Twelve divergences remain under exact live owners

The current claimed-year gate fails with twelve modelos: 126, 128, 165, 181,
184, 200, 270, 308, 309, 341, 353, and 576. The eleven non-200 divergences are
owned by `registry-temporal-coverage` `W02.P05.S51`. Modelo 200 is owned by
`aeat-export-fragment-generator-authority` `W04.P08.S22` and `W04.P08.S34`.
No implementation work is orphaned, and reviving the old umbrella rows would
duplicate those active homes.

### release-predicate | high | Registry validation is green while completeness is red

The canonical application registry verifier passes for 58 modelos and 111
revisions. The stricter cross-authority closure predicate remains correctly
red: only one revision is currently satisfied and 110 are refused, principally
because source-connectivity evidence is unmeasured or missing. The open final
release-gate row in `registry-completeness-closure` therefore remains open.

### registry-tests | medium | Collection failure is stale consumer relocation

The registry test tree currently stops during collection because three tests
still import names from the intentionally inert `domain.user_profile` facade.
This is consumer convergence after a no-compatibility relocation, not a reason
to restore the facade and not evidence that the registry validator itself
fails.

## Recommendations

- Treat the active temporal, export-authority, and completeness rows named
  above as the only implementation owners.
- Keep the archived tracker archived and cite this audit whenever its obsolete
  ownership wording is encountered.
- Keep the completeness plan open until its real closure predicate passes.
- Move stale registry-test consumers to the canonical concrete user-profile
  modules without adding aliases or re-exports.
