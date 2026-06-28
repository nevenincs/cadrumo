---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S56'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-compensation-consultation-research]]'
  - '[[2026-06-02-live-iva-persistent-failure-team-brief-audit]]'
---

# `live-iva-compensation-wallet` `W06.P15.S56` discovered entrypoint repair

## Description

Implemented the first repair after re-grounding the feature failure:
authenticated Pre303 HTML is now inspected for an official cartera entrypoint
before the driver falls back to the configured direct wallet selector route.

## Changes

- Added `discover_iva_compensation_wallet_entrypoint` to identify AEAT wallet
  links/forms whose path matches the centralized cartera path and whose host is
  one of the audited AEAT wallet hosts.
- Added a guarded dynamic-entrypoint open path that permits only GET navigation
  to the discovered AEAT wallet URL and then reuses the existing wallet execute
  gate.
- Added redacted wallet-entrypoint diagnostics to wallet page-shape context.
- Enrolled the new browser action label in centralized
  `external_constants.toml`.
- Added offline tests for discovery, host rejection, diagnostics, and guard
  allow-list coverage.

## Outcome

Focused local gates pass. This is not accepted as production readiness. The live
feature remains failed until an operator-observed read-only AEAT run proves that
the discovered Pre303/cartera path or declaration-query extraction yields the
declarante's compensation-relevant AEAT state.

## Safety

The implementation does not add any filing, payment, confirmation, represented
third-party, or tax-return submission action. The only new browser action is
`wallet-discovered-entrypoint-open`, and it is constrained to audited AEAT
wallet hosts and the centralized cartera path. Query strings and input values
are excluded from diagnostics.

