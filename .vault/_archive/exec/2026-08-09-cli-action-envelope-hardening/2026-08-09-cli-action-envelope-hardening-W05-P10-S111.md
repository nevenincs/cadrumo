---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2ef3a4e154c336e23ce721f560041062958677b3aa81f8200c07e1bce9e3596f'
step_id: 'S111'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate core output-rendering recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/core/output_rendering.py`

## Description

- Audit the declared module for refusal producers carrying authored prose or an unresolved recovery.
- Confirm each producer's locale key resolves in all four catalogues.
- Confirm the module contributes no action-census candidate.

## Outcome

- The module raises exactly two errors and both are already in the target shape. The output-format refusal carries the rejected format name and the accepted set as machine facts under its registered refusal key; the residual-scalar rendering failure carries the offending type name under its registered internal-error key. Neither carries an authored sentence and neither carries a recovery.
- Both keys are present in Catalan, English, Spanish and Hungarian, so neither producer can fall through to a bare key or to English.
- The module contributes zero rows to the action census, which is the expected result: a census candidate is a site that constructs executable recovery or continuation guidance, and neither of these failures can bind one. A format the operator typed is rejected against a closed enum, and an unserialisable residual type is an internal defect. Both are correctly terminal at this layer.
- The no-recovery half of the contract is not this module's to carry. `core` cannot import the application-owned verdict models without inverting the layering, so a core producer's obligation ends at a locale key plus machine facts, and the typed terminal projection is made at the CLI exception boundary by the application-layer precondition owner. That boundary already consumes registered core errors generically.
- The owning test module passes.

## Notes

- Satisfied by construction rather than by migration in this Step. Recording the reason matters: a later reader comparing the Step title against an empty diff should not conclude the work was skipped. The producers were already locale-keyed, and the row's remaining obligation was to prove it rather than to change it.
- The box is deliberately left unchecked. The rehoming ledger owns one constructor row for this module keyed to this Step, and because the ledger records every construction of an error qualname rather than only prose-bearing ones, the row cannot leave `migration_required` while the constructor exists. Checking the owner would add to a gate already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` findings naming twelve already-closed producer Steps; the blocking analysis and pending decision are recorded in the rehoming ledger owner-closed audit. The ledger writer was not run and no allowlist entry was added.
- Nothing could be committed: the repository index lock has been held by a dead process since the previous evening. The lock was left untouched as required, so this record is on disk and uncommitted.
- No carry-forward.
