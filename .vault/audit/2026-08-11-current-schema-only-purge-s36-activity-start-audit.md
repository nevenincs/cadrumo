---
tags:
  - '#audit'
  - '#current-schema-only-purge'
date: '2026-08-11'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0fa79da90165319492b3c997cfc8e85834e0fb5b405ad5ff7f6dae4af209af7a'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
  - "[[2026-06-13-first-filer-attestation-adr]]"
---
# `current-schema-only-purge` audit: `S36 activity-start UNCONTRASTED closeout review`

## Scope

Formally reviewed `W03.P07.S36` against the accepted `live-iva-compensation-wallet` and `first-filer-attestation` decisions. The audit covered the first-period predicate and lazy wallet reconciliation path in `src/cadrumo/application/modelo/_iva_wallet_gate.py`, the closed decision-reason identity in `IvaCompensationDecisionReason`, persistence through `IvaWalletDecisionRepository`, the direct real-behaviour proof in `test_iva_wallet_activity_start_advisory.py`, and the English, Spanish, Catalan, and Hungarian operator catalogues and CLI projection.

The review specifically tested whether the advisory is narrowed to a zero grounded only by the declared activity-start fact; whether authority-backed zero decisions bypass that advisory; whether the stamped decision is created before persistence; whether an absent or invalid activity-start date still fails closed; whether the persisted reason is a closed locale-neutral identity; and whether every operator rendering resolves the identity through a locale key.

## Findings

No critical, high, medium, or low S36 finding was identified.

The trigger is narrow. `_require_first_period_zero_decision_grounded` returns unchanged for non-first-period decisions and for decisions carrying concrete zero authority. It assigns `FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED` only when the decision is a non-authority first-period zero and the profile/registry partition proves all relevant Modelo 303 dependencies pre-activity. The lazy reconciler calls the domain reconciler with `persist=False`, applies this grounding and reason transformation, and only then saves the final decision. The direct persistence proof confirms the stored decision equals the transformed decision.

Absence remains fail closed. Missing or unparsable `censo.activity_start_date` makes the activity-start predicate false; the reconciler therefore produces the blocked `NO_USABLE_AUTHORITY` identity with no selected amount, and the direct proof confirms that blocked decision is what is persisted. The implementation adds no contrast gate and mints no AEAT authority.

The reason is a closed persisted identity rather than operator prose. `FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED` is admitted by the strict decision model, exported through the domain package, preserved in replay identity, projected by the live wallet CLI through `application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted`, and populated with explicit uncontrasted wording in all four locale catalogues.

Focused verification: `test_iva_wallet_activity_start_advisory.py` passed 2 tests; the two pure reconciliation controls for AEAT-wallet zero and seeded-local zero passed; scoped Ruff and `git diff --check` passed. One broader concrete-zero engine test reached the known unrelated annual-Orden S59 failure, `M303 annual Orden activity requires a canonical orden_id`, after the wallet gate. A second broader seed-boundary test stopped before the S36 gate because the current inflight seed-recurrence path returned no decision and raised `iva_wallet_not_seeded`. A CLI history test stopped before reason rendering because concurrent history-model fields `provenance` and `register_status` were missing. These reds do not exercise or contradict the S36 trigger, persistence, identity, or locale contracts, but they bound this audit: high-level formula and full CLI-history end-to-end proof are not green in the shared worktree.

## Recommendations

Final verdict: PASS for `W03.P07.S36`; the activity-start UNCONTRASTED advisory is correctly narrowed, persisted after transformation, fail-closed on absence, bypassed by concrete authority, represented by a closed reason identity, and localized for operators. S36 may be closed. Do not treat this verdict as clearing the unrelated annual-Orden S59 work, the inflight seed-recurrence path, or the concurrent CLI history-model drift.
