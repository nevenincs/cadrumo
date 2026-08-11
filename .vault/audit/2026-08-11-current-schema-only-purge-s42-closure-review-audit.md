---
tags:
  - '#audit'
  - '#current-schema-only-purge'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:713e7440d37612231662ff7ff0dbb2a6e374e11a332bf5dd22b732698f01647e'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
  - "[[2026-08-10-current-schema-only-purge-adr]]"
  - "[[2026-08-11-current-schema-only-purge-s42-operator-manual-audit]]"
---
# `current-schema-only-purge` audit: `S42 operator-manual carry closure review`

## Scope

Reviewed `W03.P07.S42` after remediation of every finding in the earlier operator-manual carry audit. The review covered the complete production caller census for `prepare_observation_envelope`, the exact normalization intent at each admitted caller, the operator-manual persistence boundary, and the live IVA-wallet consumer that must refuse unreadable prior Modelo 303 evidence instead of laundering it into a first-period zero.

The implementation remains caller-owned as required by the accepted current-schema amendment. No generic repository-time disposition screen or compatibility path was introduced. Tests use production imports and real encrypted persistence; no fakes, mocks, stubs, patches, monkeypatches, skips, or expected failures were added.

## Findings

No open findings.

The previous high-severity caller-population gap is closed. `test_observation_carry_ingress_caller_gate.py` now scans the complete `src/cadrumo` production package, excludes test trees, requires the discovered caller set to equal the reviewed population, and validates the exact literal or conditional expression assigned to each caller. A temporary unreviewed caller under `entrypoints` with literal `normalize_m303_carry=False` failed the gate with an explicit `unreviewed` identity; after removing the probe, the four-test gate passed.

The previous scan-boundary finding is closed by the same repository-wide production traversal. A caller outside `application` is now visible and cannot pass merely by spelling the keyword.

The previous live-consumer proof gap is closed. The source mesh now carries the canonical bienes-inversion register derived by `TransactionCatalogueRepository.migrate_iva_deduction_authority` into `LedgerIvaAggregationSourceResolver` only for revisions declaring `ledger_iva_aggregation`. The real `test_unreadable_prior_303_observation_cannot_prove_a_first_period_zero` path passes and reaches the intended typed IVA-wallet refusal instead of failing earlier on missing investment authority.

Focused verification passed: five S42 caller/operator-policy tests, the four-test clean caller-gate rerun, and the live wallet-consumer test. Ruff and the focused static caller-gate BasedPyright run passed. `git diff --check` passed for the reviewed gate. File-wide BasedPyright on `_calculation_actions.py` retains two pre-existing M210 diagnostics outside the changed source-mesh region; no diagnostic points at the S42 remediation.

## Recommendations

Mark `W03.P07.S42` complete. Preserve the exact reviewed caller set as the author-time admission boundary: any future caller or intent expression must fail until its normalization authority is explicitly adjudicated.
