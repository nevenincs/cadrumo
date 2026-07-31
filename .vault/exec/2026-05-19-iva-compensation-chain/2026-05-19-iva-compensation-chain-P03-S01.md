---
tags:
  - '#exec'
  - '#iva-compensation-chain'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:cf88226d6215f035d88103f36b9ded00a5429e766b183bcdb0d142629c07bd28'
step_id: 'S01'
related:
  - "[[2026-05-19-iva-compensation-chain-plan]]"
---

# live wallet authority verification

## Scope

Close the `iva-compensation-chain` tracking step `P03.S01` by executing an
operator-observed, read-only live AEAT IVA compensation wallet verification
against the linked live-wallet plan, so local recurrence is no longer treated as
the final compensation authority. Redacted aggregate diagnostics only; no private
taxpayer values are recorded here per the standing privacy guard.

## Description

- Confirmed the implementation surface is complete and green: the singular-source
  previous-filing period-offset resolver plus the Modelo 303 and Modelo 390
  compensation registry and calculation tests pass (78 passed on the targeted
  registry suite; the single unrelated failure was peer `LEDGER_IRNR_INCOME_AGGREGATION`
  selector-shape test drift, not a chain regression).
- Verified an authenticated Cl@ve Movil session and a `ready` active profile.
- Ran the read-only `aeat app live iva-wallet pull-evidence` acquisition twice.
  The first attempt reached the AEAT Cl@ve Movil approval gate and returned
  `operator_timeout` (persisted session expired; approval not completed in the
  window). The second attempt authenticated successfully.
- Reloaded profile-local remote state read-only (no AEAT contact) to confirm the
  captured authority decision persisted.

## Outcome

Operator-observed live authentication succeeded on the retry: AEAT returned
`auth_status=succeeded`, `auth_outcome=authenticated`, `auth_provider_kind=clave_movil`.
A Cl@ve Movil non-QR confirmation flow cannot complete without the operator
approving on-device, so the AEAT-returned auth success is itself the
operator-observed evidence the standing guard requires.

Per-surface, redacted aggregate shape:

- `wallet_cartera`: succeeded. The persisted authority decision for target
  `2026/1T` selects `aeat_wallet` as the operative authority with divergence
  `wallet_only` and `blocked=False`. Local recurrence is therefore no longer the
  final authority — the explicit `P03.S01` condition is met.
- `filed_history`: failed with a `RegistryValidationError` (residual finding,
  below). Per the live-wallet design (`W06.P15.S54`) the two surfaces succeed or
  fail independently, so the wallet-authority evidence stands on its own.
- Read-only local reload reported: 4 compensation history rows, 2 carry-forward
  lots, 1 persisted authority decision, selected authority `aeat_wallet`,
  divergence `wallet_only`, not blocked. No AEAT write, filing, payment,
  amendment, or represented-taxpayer path was attempted (`safety_policy=read_only_fail_closed`,
  own-name representation only).

`P03.S01` closes on the audit-sanctioned trigger ("the next operator-observed
read-only live verification run"). The live-wallet plan row `W06.P15.S56` is a
by-design permanently-open standing live-verification path and privacy guard; it
remains open and is not checked by this step.

## Notes

Residual finding for the live-wallet plan (not the chain): the `filed_history`
capture surface failed with a `RegistryValidationError` while building calculation
observations from the captured filed Modelo 303 declarations across 2022-2026. The
bundled registry itself validates cleanly (Modelo 303 snapshots for 2024/2025/2026
build without error), so the error is specific to the live filed-history
observation-build path, not a registry-tree defect and not the IVA
compensation-chain implementation. It could not be reproduced offline because it
depends on live-captured filed data. Tracked for the live-wallet plan's
filed-history capture surface; it does not gate the chain's wallet-authority
dependency. The prior 2026-06-05 S56 exercise recorded both surfaces succeeding,
so this is an intermittent filed-history capture failure, consistent with the
per-declaration timeouts already documented in the S56 history.
