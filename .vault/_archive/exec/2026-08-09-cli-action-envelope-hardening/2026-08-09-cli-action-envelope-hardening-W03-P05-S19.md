---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f6478231cf71181944db4e68ff4b5582e3907b7c875152513c3655e03044b6c2'
step_id: 'S19'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Prove every storage policy condition identity evidence action status and binding set

## Scope

- `src/cadrumo/application/tests/test_storage_write_policy.py`

## Description

- Calibrate semantic discovery for storage-policy verdict ownership, route
  classification, settings evidence, and existing proof coverage, then confirm
  every producer and consumer with exact searches.
- Freeze one scenario key for every live `StorageWritePolicyCode` identity and
  reconcile the matrix bidirectionally without a hard-coded count.
- Assert each allowed classification as a complete serialized decision with no
  verdict.
- Assert both refusing routes with fixed condition, evidence, action or
  no-recovery, complete binding, missing-input, and conditionality records.
- Tie explicit-route evidence to the real `Settings` fields and environment
  authorities.
- Prove the action identity and live-classification denominator gates fail under
  temporary production mutations, then restore the producer unchanged.
- Run focused, adjacent action-contract, live-resolution, real-root integration,
  format, lint, typing, and diff gates.
- Remediate the independent review finding that the first matrix did not join to
  the live classification denominator.

## Outcome

Every current write-policy classification has exactly one canonical scenario
key and exact production-observation proof. The five allowed outcomes carry no
failed verdict. The cold-root refusal emits `profile.active` with
`profile.active.storage_route`, `operator.profile.create`, and exactly one
missing `profile_name` argument. The explicit database refusal emits
`storage.route.active_bucket` with settings-authoritative route evidence, no
action arguments, `not_applicable`, and the explicit `operator_decision`
no-recovery outcome. Both refusing rows prove action-versus-no-recovery
exclusivity. No resolved binding was invented because this producer exposes
only a missing binding and an empty binding set.

The focused module passed 16 tests. The combined storage and operator-action
contract lane passed 55 tests, live action resolution passed 19 tests, and the
real root integration lane passed 11 tests. Targeted Ruff, format, basedpyright,
and diff checks passed. Independent Terra xhigh review closed its sole high
finding after the exact live-enum reconciliation and its failing mutation proof.

## Notes

The configured full-tree basedpyright run remains red on 16 concurrent
diagnostics outside this Step; the S19 target reports zero diagnostics. A first
adjacent catalogue run failed while peer work had added a `work_unit_id`
specification without its test expectation; the peer change subsequently
landed and the complete adjacent lane passed. Clean-root recovery dispatch and
retry remain exclusively `W03.P05.S20`.

Shared preservation commits and merges advanced `HEAD` while this Step ran and
included the reviewed test and audit. This executor did not stage or commit and
did not touch `.git/index.lock`.
