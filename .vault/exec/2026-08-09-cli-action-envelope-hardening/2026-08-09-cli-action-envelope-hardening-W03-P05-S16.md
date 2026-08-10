---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:608ab48b6a70067d07343250bab9b07c4ffd1e9ec99005f99ab7743654afbcf7'
step_id: 'S16'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Replace storage write-policy recovery hints with typed failed-condition verdicts

## Scope

- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/tests/test_storage_write_policy.py`

## Description

- Locate the application write-policy authority, canonical action models, action
  catalogue, and root transport consumer through calibrated semantic discovery
  and exact symbol confirmation.
- Replace the policy-owned free-form recovery hint with strict failed-condition
  verdicts and stable condition and evidence identities.
- Emit `profile.active` for cold-root writes with factual route evidence, the
  canonical `operator.profile.create` reference, and a typed missing
  `profile_name` binding.
- Emit `storage.route.active_bucket` for explicit database routing with factual
  override evidence and an explicit operator-decision no-recovery outcome.
- Enforce that refusing decisions require a verdict and allowed decisions carry
  none.
- Extend direct production-import tests for both refusal branches and the
  allowed active-bucket branch.
- Run focused and adjacent tests, formatting, lint, strict typing, exact
  consumer inventory, and independent Terra xhigh review.

## Outcome

The application producer now emits immutable precondition verdicts without
localized recovery prose or executable command strings. The cold-root verdict
is conditional because `profile_name` is genuinely absent; it does not invent a
placeholder. The explicit database URL branch does not misrepresent an
environment mutation as an executable CLI action. Existing route
classification, refusal codes, message identities, and allowed/refused policy
decisions are unchanged.

The direct application suite passed 10 tests. The combined storage-policy and
canonical action-contract lane passed 49 tests. Targeted Ruff check and format,
targeted BasedPyright, and diff checking passed. Full BasedPyright reached one
unrelated peer-owned unused import in `application.user_profile`; both S16 paths
reported zero diagnostics.

Fresh Terra xhigh review after the S17 transport cutover closed the prior high
runtime integration finding. Both real root refusal routes now attach their
typed verdict projections, the requested live leaf is retained, and no legacy
`refusal_context` compatibility shim was restored. The root typed-projection
integration suite passed all 11 tests. S16 is complete.

## Notes

- The adjacent root refusal integration module ran 20 tests: 16 passed and four
  failed. Two failures are the S17 `refusal_context` runtime break on the
  cold-root and explicit-URL paths. Two are concurrent live-surface census drift
  for newly added counterparty and evidence leaves; no S16 path owns those
  classifications.
- The first adjacent invocation selected zero tests under the default unit
  marker and was discarded as evidence; the corrected integration-marker run
  produced the results above.
- No S17 CLI transport, S18 boundary, S19 exhaustive policy proof, or S20
  recovery-and-retry implementation was absorbed into this Step.
- The later S17 review is the closure authority for the former root-cutover
  finding. Its broader producer lane passed 56 tests; three remaining failures
  are peer-owned legacy-suggestion and newly introduced root-census work, not
  S16 behavior.
- No commit was made. The shared zero-byte Git index lock was left untouched in
  accordance with the absolute worktree-safety rule.
