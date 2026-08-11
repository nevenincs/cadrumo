---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:4efd837f7de39cc2389d90d39776764ee52095cf89775e5132cb16ef333f84f7'
step_id: 'S33'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# W05.P09.S33 - Replace provisioning optional-extra recovery prose with typed failed-condition facts and explicit no-recovery outcomes including the local-model stored-without-extra row and hand the changed dependency projection to S89 without retained remediation compatibility

## Scope

`src/cadrumo/application/provisioning.py`; directly owned provisioning application tests.

## Description

- Replace the seven provisioning outcome DTOs' presentation and remediation fields with immutable machine facts and an optional typed precondition verdict.
- Declare closed provisioning failed-condition identities covering dependency availability, runtime reachability, hardware and contention measurements, model ownership, and model lifecycle failures.
- Emit an explicit operator-decision no-recovery outcome for every failed or refused producer branch; preserve a null verdict for healthy and successful outcomes.
- Keep local-extra-present/model-absent and stored-model-present/local-extra-absent as distinct predicates and evidence sets.
- Remove provisioning dependence on the core optional-extra feature label and install command.
- Hand the changed facts and verdict projection to S89 without a compatibility field or alias.

## Outcome

The application provisioning boundary now returns locale-neutral facts and typed closed outcomes. All seven former detail/remediation DTOs reject silent failures and reject verdicts on successful states. No provisioning producer emits a raw command, install hint, or recovery sentence.

Verification completed:

- 67 focused provisioning real-behavior tests passed.
- 110 combined provisioning and operator-action model/catalogue tests passed.
- Ruff check and formatting passed for the producer and directly owned tests.
- Basedpyright reported zero errors and warnings for the producer and directly owned tests.
- The recovery rehoming ledger validated 238 rows.
- Python compilation and Git diff whitespace checks passed.

## Notes

S89 owns the coordinated CLI schema and rendering consumer cutover. This execution remains open for independent review; the plan checkbox was not changed.
