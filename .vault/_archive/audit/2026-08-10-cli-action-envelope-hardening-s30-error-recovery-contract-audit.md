---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:409a0fcc0fb1a2dc8a5da8dfb2a989e17eca790c417b9e0c414bc9f089fa06a7'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S30 error recovery contract independent review`

## Scope

Independently reviewed S30 after the focused contract test changed `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`. The review covered the real blank-state refusal, the registered error boundary, the application action catalogue, the live Click input projection, and strict error-envelope parsing.

## Findings

### canonical-projection-anchor | medium | Initial test selected the recovery target from emitted payload

The first S30 version rebuilt the target schema from the emitted `target_command_key`. A producer and payload could drift together and preserve a passing shape comparison, so that did not prove the action came from the canonical catalogue.

Remediation resolves `action.action_id` with production `lookup_action`, derives the schema from the declaration, and compares the emitted key, live Click path, declaration binding names, and live target parameters. The independent review passed after this change.

### strict-refusal-envelope | medium | Partial payload inspection did not fail extra fields

The first version validated the nested action but did not enforce the complete outer spine or reject unknown nested error members.

Remediation asserts the exact outer keys `schema_version`, `command`, `active_profile`, `status`, `error`, and `notices`; it validates the action from its JSON wire form and passes the resulting value to `ErrorEnvelope.model_validate(error)`. This makes unexpected error guidance, including retired suggestion-style fields, a failure.

### deferred-chain-coverage | low | S30 boundary is intentionally narrower than campaign closure

The real `REFUSED_CLI_BOUNDARY` proof includes a conditional profile-create input. The follow-on wizard missing-input refusal and the stale retired error-registry-suggestion-test rationale are genuine campaign gaps, but they are not S30 implementation defects.

The plan now assigns the wizard missing-input chain to amended S37 and the retired test-reference cleanup to amended S45. This audit records those assignments rather than treating a single root refusal as campaign-wide closure.

## Recommendations

Keep the S30 proof anchored in a registered real refusal and in the catalogue declaration, never in a payload-provided target. Keep full declared-observed recovery coverage and negative-recovery-retry journeys in the W06 closure work. Complete amended S37 and S45 before making any broad actionable-chain completeness claim.
