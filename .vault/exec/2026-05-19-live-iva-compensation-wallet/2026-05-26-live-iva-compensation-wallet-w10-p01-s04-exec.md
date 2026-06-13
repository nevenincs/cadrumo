---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---



# `live-iva-compensation-wallet` `W10.P01.S04`

Added the static regression gate for the live IVA wallet localization boundary.

- Modified: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-26-live-iva-compensation-wallet-convention-regrounding-audit.md`

## Description

The wallet test suite now parses the production wallet adapter AST and fails if
`SedeNavigationError` or `SedeParseError` is constructed with a raw positional
literal or f-string without an explicit `translated_message` keyword. This
turns the W10.P01.S03 wallet migration into an enforceable regression gate for
the legally sensitive live-read surface.

This S04 slice also builds on the existing W10.P01.S02 static gate that blocks
new unclassified production exception classes deriving only from Python
builtin exception bases. Together, the two gates cover the wallet's immediate
localization boundary and the central AEAT exception-family inheritance rule.

The broader repository still has a large legacy raw-message inventory. This
gate is intentionally scoped to the IVA wallet adapter because the remaining
raw-message clusters need phased allowlist and migration work rather than a
single broad failing test that would block unrelated changes without a clean
remediation path.

The official plan-step CLI could not close `W10.P01.S04`; it returned `Step
'W10.P01.S04' does not exist in this plan`. The W10 row was closed manually
after reproducing the L4 step-addressing limitation.

## Tests

Passed:

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings`
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
