---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fb211f691d5dd9730613249e9df766b9a004a2188f3f28a9382e9f1250214680'
step_id: 'S54'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# record the operator re-authentication step (Cl@ve Móvil) required to re-acquire discarded live captures as an explicit OPERATOR action in the Step record, not an automated action

## Scope

- .vault/plan/2026-08-07-canonical-identifiers-plan.md
- src/cadrumo/application/config_reset.py
- src/cadrumo/application/operator_actions/_catalogue.py

## Description

- Read the S51/S52 decisions that can require the application-level discard in S53.
- Read the
esume_config_reset and BucketMaintenanceService.delete contracts: deletion is confirmed application work, not a filesystem operation.
- Read the canonical operator-action catalogue and the Cl@ve Móvil authentication evidence.

## Outcome

S54 records the recovery boundary without asserting that any reset, deletion, or re-derivation has occurred.

S53 is currently blocked: CADRUMO_SECRET_PASSPHRASE is unavailable in this noninteractive session, so profile-storage browse cannot open. No affected database can therefore be confirmed and no discard can proceed.

**OPERATOR action:** Only after S53 has completed its confirmed application-level discard for an affected profile, the operator must use the canonical operator.auth.login action with the configured Cl@ve Móvil provider and complete its human approval. That fresh authentication is required before the operator re-acquires the discarded live captures through their supported retrieval flow.

This record does not automate authentication, does not embed a command spelling in place of the typed action, and does not authorize a filesystem-level delete. No profile database or capture has been discarded by S54.

## Notes

operator.auth.login is the canonical action identity and resolves to the config.auth.login command schema. The existing receipt/auth evidence documents Cl@ve Móvil as a human approval flow; it is therefore an explicit operator boundary rather than a background continuation.
