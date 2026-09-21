---
tags:
  - '#audit'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:1551b84c047a7ca2d77ea8c816fe26b9f630b779c6c38afef2a52ef3a2fe122c'
related:
  - "[[2026-09-21-assets-core-plan]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
---

# `assets-core` audit: `Integrated assets-core review`

## Scope

Reviewed Phase P01 across the accepted lifecycle decision, its code/reference
grounding, the current amortization-routing regression, inventory separation,
execution evidence, and the transition into the persisted schedule work. Source
commits reviewed: `d50d31373a`, `33b7c8492d`, and `376669fb66`.

Reviewed Phase P02 across the accepted lifecycle and cost-basis decisions, the
typed asset/revision/claim contracts, 2025 normal and simplified authority
tables, deterministic day-count schedule, encrypted CAS-guarded persistence,
restart reconstruction, and focused verification evidence.

## Findings

### phase-01 | low | unsafe full-cost routing remains intentionally pinned

The regression correctly proves that an unscheduled acquisition still reaches
casilla 0208 at full base. This is evidence for the P03 collision fix, not a
supported outcome. The accepted atomic-delivery boundary prevents the future
asset persistence or API from being presented as complete until resolver and
filing ownership land with it.

Result: PASS. No critical or high findings.

### phase-02 | low | shared namespace-order tripwire has a concurrent omission

The assets namespace declaration, enrollment, and expected-order entry agree.
The global expected-order test continues to fail later in the sequence because
the concurrently added `withholding_workflow` namespace is absent from that
test's expected tuple. Assets work must not patch the income lane's ownership
gap; the focused assets persistence, registry-adoption, grammar, and encryption
checks pass.

Result: PASS. No critical or high findings. The unrelated shared-test failure is
recorded as an integration dependency rather than hidden or overwritten.

## Recommendations

Retain the regression unchanged through P02. In P03, add the positive scheduled
charge and scoped competing-claim refusal before replacing the unsafe behavior.
Do not weaken the test to make an intermediate backend slice appear complete.

For P03, resolve authority rows through the registry-backed provider rather
than accepting a caller-invented rate, preserve the single M130 casilla-02
owner, and displace the proven unsafe transaction-ledger 0208 route only within
the scoped acquisition/depreciation collision.

