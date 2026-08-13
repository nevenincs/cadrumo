---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5d7cf9c2f4a3a7d3a5fea80749142f1c6f821e607ca25ce6385d42ac1f2feac0'
step_id: 'S110'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate application state-projection recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/state_projection.py`

## Description

- Scan the declared module for refusal producers by syntax tree and classify each by reachability.
- Classify the single rehoming ledger row this Step owns against the module's current source.

## Outcome

- The module raises three times and none of the three is an operator-facing refusal. Two are totality assertions that run at import: they compare a closed enum against its projection mapping and fail the process if a member lacks an action axis or a binding-readiness locale key. The third guards a mutually-exclusive argument pair on the projection assembler. All three are developer invariants whose only reachable audience is whoever is editing the module, and none can bind an operator recovery.
- The single ledger row this Step owns is `reference` role and sits in the readiness binding helper, which catches a profile-binding resolution error rather than raising it. The module is a consumer at that site, so the correct final disposition is the non-producer reference kind.
- The two import-time assertions are worth keeping exactly as they are. They are the reason a new binding source kind cannot ship without both its action axis and its readiness locale key, which is the totality guarantee the readiness projection depends on; converting them to a localised refusal would weaken a build-time failure into a runtime one.
- The owning test module passes in full.

## Notes

- Satisfied by construction, with one classification stated rather than assumed. The three raises are bare built-in exception types outside the registered error hierarchy, so they carry no code, no key and no context. That is defensible for an import-time totality assertion and for an argument-pair guard, because neither is reachable from an operator surface. It is a classification, not a proof: the campaign's fixed-point closure asks that no site be left unclassified, and these three will need to be recorded as terminal developer invariants rather than silently passed over. No row currently states that.
- The setup selection run alongside this one carries nine failures from a peer campaign's newly-required taxpayer residence-scope profile input; they are outside this scope and the module was not modified.
- The box is deliberately left unchecked. This Step is a rehoming ledger owner, and the gate is already red at HEAD with 151 `E_REHOMING_OWNER_CLOSED` findings naming twelve already-closed producer Steps; the blocking analysis and the pending decision are recorded in the rehoming ledger owner-closed audit. The ledger writer was deliberately not run, no allowlist entry was added, and no closed Step was touched.
- Nothing could be committed: the repository index lock has been held by a dead process since the previous evening. The lock was left untouched as required, so this record is on disk and uncommitted.
- No carry-forward.
