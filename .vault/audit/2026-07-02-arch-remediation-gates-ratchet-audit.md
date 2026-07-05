---
tags:
  - '#audit'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
---

# `arch-remediation-gates-ratchet` audit: `implementation review`

## Scope

Review of the repaired Import Linter ledger, the new ledger ratchet tests, and
the vault execution records for the gate-ledger repair plan. The review checked
that the broad application-to-adapters wildcard is absent, the remaining
module-level pins resolve on disk, the count-ratchet baselines match the
post-repair ledger, no plan metadata was added to runtime test code, and the
required gates run cleanly.

## Findings

No open findings.

### follow-up-profile-activity-test-boundary | low | application test no longer imports CLI test helpers

Reviewed the 2026-07-05 ratchet follow-up that rewired
`test_review_profile_activity_staleness` away from the CLI test-support
package. The test still provisions a real encrypted profile bucket and mutates
the relation-scoping `activities.description` fact through application
profile primitives; it no longer adds an application-to-entrypoints edge to the
layered contract. Focused pytest passed, and the layered linter rerun no longer
reports an application-to-entrypoints violation. The layered contract remains
red on the broader application-to-adapters inventory, so this is a boundary
reduction only, not program closure.

## Recommendations

Keep the `aeat.tests.secure_sql -> aeat.adapters.**` wildcard under explicit
review in later inversion work. It remains justified here because the helper is
a shared secure-storage test utility that imports real persistence adapters.
