---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ea5d6b03b22ec2879c8fed5bad73f1d38e36bc407596ea4a2515003581e08891'
step_id: 'S14'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Escalate the advisory to a verify-stage refusal only for a row declaring a cuota-less category with no taxable base

## Scope

- `src/cadrumo/application/modelo`

## Description

- Identify the one missing-substrate shape whose under-declaration direction is certain.
- Add the verify-stage finding builder, BLOCKING, grounded in the duty to declare.
- Wire it beside the evidence gate in the verification collector.
- Assert the boundary with four over-blocking controls.

## Outcome

A category in the cuota-less set carries no cuota by law, so the taxable base is
the row's only possible contribution to the return. A row declaring such a
category with no base contributes nothing at all while representing, in the
ledger, a declared operation - the base casilla is understated by exactly that
operation's amount, every time.

That certainty is what earns the escalation, and equally what bounds it.
Everywhere else in the missing-substrate family the direction is ambiguous: a
cuota-bearing row still contributes through its quota, and a renta row falls
back to its bank cash. Refusing those would block filings that are merely
imprecise, so they stay advisory.

BLOCKING rather than WARNING, for the reason the neighbouring evidence gate
already documents: an advisory at verify grants and freezes a gap-carrying
bundle, and the export and filing refusals then arrive after the operator has
been told the draft was fine. A non-granting verify leaves the revision in
BORRADOR, so the base can be entered and the draft re-verified.

Grounded in the obligation to declare the operation rather than in the
deduction-evidence statute the sibling gate cites. Different requirement,
different references.

## Verification

The gate and its four controls:

    uv run --no-sync pytest -q -p no:randomly -n 0 src/cadrumo/application/modelo/tests/test_cuota_less_without_base_gate.py
    6 passed in 0.41s

The surrounding verification surface, unchanged by the escalation:

    uv run --no-sync pytest -q -p no:randomly -n 4 src/cadrumo/application/modelo/tests -k 'verif or evidence or gate'
    314 passed in 63.32s (0:01:03)

## Notes

Ratified by the operator before implementation, which the Step text required.

The coverage control drives the canonical frozenset rather than a hand-listed
sample, so a category added to that set is refused the day it lands instead of
escaping a list nobody remembered to extend.
