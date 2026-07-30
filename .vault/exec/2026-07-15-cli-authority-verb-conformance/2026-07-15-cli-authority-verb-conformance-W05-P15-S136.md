---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S136'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace verify-recovery terminology with config recovery verify in the recovery contract

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Read the recovery contract in the named facade module and confirm the retired verify-recovery verb terminology is gone.

## Outcome

The named surface cites the accepted `aeat config recovery verify` verb in its periodic custody-test contract, and no `config verify-recovery` terminology survives in the module.

The internal function name that verifies a recovery mnemonic is a domain-layer symbol rather than operator verb terminology, so it is correctly untouched by this Step; the Step governs the cited CLI grammar, not the name of the function implementing the check.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
