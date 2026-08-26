---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:eb2abcdd5a330e30383c4230ed8cd438ba2190355f9aa6c0e0e1ccb957489ae9'
step_id: 'S69'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement filed-history stage, unit, refusal, partial-effect, evidence, wallet, notification, and provenance result projection

## Scope

- `src/cadrumo/entrypoints/tui/profile/sync_review.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/profile/sync_review.py`
- `verify:` `pytest src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py -m integration` -> `pass` (2 passed)

## Notes

PARTIAL DELIVERY, Step left unchecked. `FiledHistoryProgressSummaryV1` /
`filed_history_progress_summary` deliver stage (phase code), lifecycle,
terminal condition, effect, and refusal/diagnostic references -- everything
the public projection legitimately carries. Evidence, IVA-wallet,
notification, and provenance are NOT projected: the operation's public
registration (`build_filed_history_operation_registration`, using
`OperationPublicDefinitionRegistrationV1.compose_request_only`) declares no
public `result_schema`, so those facts exist only on the private
`FiledHistoryOnboardingRun` result type, unreachable from the TUI layer
without importing an application-private type -- exactly the boundary this
plan's wave forbids crossing. Closing the rest of this Step requires either
a public `result_schema` binding added to that registration (an
application-layer change outside this Step's TUI-only remit) or an explicit
decision to keep those facts CLI/MCP-only. Reported to the team lead;
awaiting direction before closing.
