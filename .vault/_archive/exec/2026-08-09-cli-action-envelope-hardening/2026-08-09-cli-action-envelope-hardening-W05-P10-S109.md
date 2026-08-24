---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:907b234fa6152160db45169299aefddac4a0dfca23b1a08b2e93f9df27c6dc3e'
step_id: 'S109'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate application setup recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/setup/_service.py`

## Description

- Scan the declared module for refusal producers by syntax tree rather than by keyword.
- Classify the single rehoming ledger row this Step owns against the module's current source.

## Outcome

- The declared module raises nothing at all. A syntax-tree scan for raise statements reports zero, so there is no producer to migrate and no prose to retire.
- The single ledger row this Step owns is `reference` role, not `constructor`. It records the authorisation-provider reservation handler, which catches that error rather than raising it. The module is a consumer of that refusal, not its author, so the correct final disposition is the non-producer reference kind.
- The provider-reserved refusal is authored in the authorisation package, which is a different Step's scope.

## Notes

- Satisfied by construction. The distinction worth preserving is that a `reference` ledger row is not weaker evidence of a producer, it is evidence of a consumer: this Step's row exists because the setup service names the error in an except clause, and no amount of migration in this module can change that row's shape.
- The owning package's test selection carries nine failures, none from this Step. All nine are a peer campaign's newly-required taxpayer residence-scope profile input, which refuses the quiet non-interactive profile creation these tests drive; the module was not modified here and a diff against the index confirms the declared scope is untouched. The state-projection selection in the same run is fully green.
- The box is deliberately left unchecked. This Step is a rehoming ledger owner, and the gate is already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` findings naming twelve already-closed producer Steps; the blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The transition to the non-producer reference kind requires the ledger writer, which was deliberately not run. No allowlist entry was added and no closed Step was touched.
- Nothing could be committed: the repository index lock has been held by a dead process since the previous evening. The lock was left untouched as required, so this record is on disk and uncommitted.
- No carry-forward.
