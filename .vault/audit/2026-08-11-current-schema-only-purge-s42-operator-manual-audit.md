---
tags:
  - '#audit'
  - '#current-schema-only-purge'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:6282e76f2adbe212621daa14c66304c5b47a281b46644c516365aabf61b77112'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
  - "[[2026-08-10-current-schema-only-purge-adr]]"
---
# `current-schema-only-purge` audit: `S42 operator-manual carry boundary`

## Scope

Audited `W03.P07.S42` against the accepted caller-owned carry-ingress policy and the retained explicit non-normalizing treatment of `record_operator_local_observation`. The review covered the complete operator writer, the static caller census, the real operator-manual M303 policy test, the canonical carry ingress, and the shared repository preparation door. It checked that operator-manual rows cannot acquire carry authority, unrelated relation prefill remains available, and tests use production imports plus real encrypted persistence without fakes, mocks, stubs, patches, monkeypatches, skips, or expected failures.

The focused S42 lane passed four tests in 20.24 seconds. Path-scoped Ruff and BasedPyright passed with zero diagnostics. An external anti-gate probe proved the author gate reds when the existing operator writer omits its keyword, but a separate fresh-context probe also proved all three gate tests remain green when an additional unreviewed production caller explicitly passes `normalize_m303_carry=False`. The existing real wallet-consumer laundering test was also executed and failed before reaching the carry decision because current shared-tree aggregation code raised `AggregationValidationError` with `injected IVA repositories require explicit bienes-inversion authority`; that lane is therefore unverified, not green.

## Findings

### non-normalizing-census | high | An unreviewed false caller passes the author gate

`test_every_production_observation_writer_states_carry_normalization_intent` checks only that every discovered call carries the `normalize_m303_carry` keyword. `test_known_compliant_observation_writers_remain_explicit` requires the two positive controls only as a subset, and `test_operator_manual_writer_remains_explicitly_non_normalizing` checks only the single named negative control. Consequently, a new production writer that explicitly passes `normalize_m303_carry=False` satisfies every gate without entering a reviewed population or stating why it is safe to produce a noncanonical M303 envelope. A fresh-context temp-tree probe added exactly that rogue caller and all three tests passed. This reopens the supply-side class the accepted amendment identifies at `src/cadrumo/tests/test_observation_carry_ingress_caller_gate.py` lines 64-100.

### production-scan-boundary | medium | The scanner does not cover the production package it claims to govern

`_APPLICATION_ROOT` points at `src/cadrumo/application`, and `_production_callers` walks only that subtree while the assertion states that every production caller is governed. A caller under another production package such as `src/cadrumo/entrypoints` is invisible even though production entrypoints already import `CalculationObservationRepository`. The current census is clean, but the static control does not enforce its stated future boundary.

### wallet-consumer-proof | medium | The live no-laundering acceptance path is not green

The new S42 real-behavior test proves the public operator writer persists an envelope with no disposition or compensation basis, proves canonical carry validation rejects its `OPERATOR_MANUAL` provenance, and proves the same rows still resolve an unrelated M390 relation. It does not traverse the wallet consumer where unreadable evidence was historically converted into first-period zero. The existing end-to-end consumer test, `test_unreadable_prior_303_observation_cannot_prove_a_first_period_zero`, currently fails earlier in aggregation at `src/cadrumo/application/aggregation/_iva_ledger.py` with an explicit bienes-inversion-authority precondition. Source inspection shows `_prior_period_carry_evidence` preserves `prior_period_observation_found=True` on validation refusal and forwards `local_evidence_found_but_unusable=True`, but current-tree runtime proof of that full path remains blocked.

## Recommendations

Make the reviewed literal-false caller population exhaustive: require the set of production callers whose keyword is literal `False` to equal the named non-normalizing controls, require all admitted positive callers to express an accepted true or modelo-conditioned intent, and fail closed on non-literal expressions until adjudicated. Prove the revised gate bites with an external rogue-false caller probe.

Expand the scan to the complete production package with test trees excluded, or add an independently enforced architecture boundary that makes `application` the only legal owner of this repository call and cite that control in the gate.

Restore and rerun `test_unreadable_prior_303_observation_cannot_prove_a_first_period_zero` through the actual wallet consumer after the unrelated aggregation fixture contract is reconciled. Do not close S42 on validator rejection alone; require both the focused four-test S42 lane and the live consumer anti-laundering lane to pass.
