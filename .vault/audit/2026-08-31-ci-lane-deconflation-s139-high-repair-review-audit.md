---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5fd344f83f9f78a15f2496df0c0ae44b3a2a11175202dba549eac3969a1aaef8'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `P05 S139 HIGH repair re-review`

## Scope

Independent final re-review of the P05.S139 HIGH repair at `2068f721e092da3b903965c9756e8d8d2e57418a`, against original S139 `a464bfa131078a1732037adc83e010e230715a02` and audit `c33701a652edd3aafce94abd1e84f0257d2c08ee`. Current HEAD was confirmed at the repair revision. Reviewed the repair diff, canonical definition and public routes, exact execution record, focused test evidence, dimensions, and policy/baseline scope.

## Findings

### s139-high-repair-review | high | The old clean-state forwarding route remains importable

The repair removes `filing_external_evidence_blockers` only from `cross_period_clean_state.py`'s `__all__`. At line 51 that module still performs `from ._cross_period_external_evidence import filing_external_evidence_blockers`, and line 1064 invokes the bound public name. Python therefore continues to expose `cross_period_clean_state.filing_external_evidence_blockers`; direct verification imported that old route and confirmed it is the identical defining object. The prior HIGH is not resolved. Alias this same-package implementation dependency privately and change the call site to the private alias, leaving the direct package export from `_cross_period_external_evidence.py` as the sole public route.

The repair record is otherwise literal and complete: ruff and format pass, collection states five tests with zero deselection, five tests pass, and 1,127 plus 130 lines remain within the unchanged 1,250 cap. Independent execution of the repaired five-test node set passed in 9.61 seconds. No plan, baseline, or threshold path changed.

## Recommendations

Resolve the remaining HIGH by importing `filing_external_evidence_blockers` under a private local name in `cross_period_clean_state.py` and calling only that private name. Verify that importing the symbol from `cross_period_clean_state` then fails while the package export continues to resolve directly from `_cross_period_external_evidence.py`.
