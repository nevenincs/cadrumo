---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:11d91e0ec89ac31e4e3e78c3fce02dd895624f0565ca0da79399db45e3921c5c'
step_id: 'S98'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# prove the M360 refund-operation source remains refused at calculation ingress and unavailable to a connected encrypted source lifecycle diagnostics/review and source-owned repeated-record export until the S97 reopening predicate is satisfied while separate manual M360 request bindings remain available

## Scope

- `dev/source_connectivity/tests/test_m360_deferral.py`

## Description

- Amend S98 through the plan CLI from an impossible positive lifecycle proof to a terminal negative proof.
- Exercise the live deferred route, advisory, absent resolver ownership, absent connected fixture, and non-projection export surface without mocks.
- Preserve the separate operator-entered M360 `manual_input` binding path.

## Outcome

The `refund_operation` source remains refused and cannot form a connected encrypted persistence, replay, diagnostics/review, or source-owned repeated-export lifecycle before S97's predicate is met. No carrier, store, resolver, or layout was added.

## Notes

- Focused pytest passed: `dev/source_connectivity/tests/test_m360_deferral.py` (3 passed). Focused Ruff passed.
- An exploratory full coverage-composition assertion exceeded the focused runner window and was not retained; the committed test uses the direct live route authorities.
- Formal self-review audit was intentionally excluded by the authorized S98 scope.
