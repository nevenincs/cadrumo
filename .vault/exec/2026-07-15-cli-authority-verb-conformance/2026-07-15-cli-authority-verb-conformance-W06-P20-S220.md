---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:635294c0fd247fd57cd5f7635aaf4eb214cdcec6468921e4c277b6178090a600'
step_id: 'S220'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run repository-wide Vaultspec checks and triage unrelated residuals honestly

## Scope

- `.vault/`

## Description

Run the repository-wide vault check across every feature, then triage the
residual output by owner.

## Outcome

Exit 0, zero errors, 14717 warnings.

Every warning is the same advisory shape, recommending that a plan reference
a research document. None is an error and none is attributable to this
campaign. The named plans are concurrent work owned by other campaigns:
the delivery-pipeline audit, the Homebrew arm64 work, the open-decisions and
operator-gates plan, the profile-bundle TUI, the scoop-runner topology and
the test-harness honesty plan.

Triaged as unrelated residual and left with their owners rather than
absorbed. No repository-wide finding blocks this campaign, and none is
claimed as fixed by it.

## Notes
