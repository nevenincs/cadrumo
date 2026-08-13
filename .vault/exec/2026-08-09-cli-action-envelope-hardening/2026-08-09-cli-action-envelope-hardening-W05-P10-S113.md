---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b1ef0f8045e7a72cb1a77e6b14b0ebd89367efa564966a79c4a41865904f7e3a'
step_id: 'S113'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate domain-bucket recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/domain/buckets/_errors.py`

## Description

- Audit the declared module for refusal producers carrying authored prose or an unresolved recovery.
- Classify the rehoming ledger rows this Step owns against the module's current source.
- Locate the bucket-domain producers that fall outside the declared scope and establish who owns them.

## Outcome

- The declared module raises nothing. It is a pure taxonomy of nine exception classes over the bucket-event-history and bucket-maintenance surfaces, each carrying a docstring and no body, and it holds no recovery attribute, no command literal and no message construction.
- All seven rehoming ledger rows this Step owns are `reference` role, not `constructor` role. They record the class definitions themselves, not any construction of them, which is consistent with a taxonomy module and is the evidence that the module never held recovery authority to retire.
- The module contributes zero rows to the action census, as expected for a surface that constructs nothing.
- The wider bucket domain and its maintenance tests pass.

## Notes

- Satisfied by construction. The absence is structural and worth stating plainly: refusals over bucket state are raised by the application services that operate on buckets, not by the domain's exception declarations, so a later reader should not expect producers to appear here.
- Scope boundary, stated rather than assumed. Two producers in the bucket domain do still carry English f-strings: the event-identity mismatch and the catalogue-key mismatch guards in the event module. They are outside this Step's declared scope, carry no rehoming ledger row and contribute no census candidate, because both are internal derivation invariants rather than operator-facing refusals. That classification is defensible, but it is a classification and not a proof: the standing campaign goal asks that every reachable failed precondition emit a stable condition identity, and these two emit an authored sentence. If either is ever reachable from an operator surface it needs its own row. No row currently covers them.
- The box is deliberately left unchecked. This Step is a rehoming ledger owner, and the gate is already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` findings naming twelve already-closed producer Steps; the blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The correct final disposition for these seven rows is the non-producer reference kind, but that transition requires the ledger writer, which was deliberately not run. No allowlist entry was added and no closed Step was touched.
- Nothing could be committed: the repository index lock has been held by a dead process since the previous evening. The lock was left untouched as required, so this record is on disk and uncommitted.
- No carry-forward.
