---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d2ede33d526548f7eb5c8a852b2e0ac318cd8b28a881f62774bef2839ff185b6'
step_id: 'S30'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Prove registered error recovery resolves against the live command and input surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`

## Description

- Ground the proof in the accepted action-envelope ADR, the approved plan, semantic discovery, `resolve_cli_precondition_action`, `lookup_action`, the live input-schema builder, and `ErrorEnvelope`.
- Exercise real blank-state `ledger.list` dispatch with isolated storage and schema-derived argv, observing the registered `REFUSED_CLI_BOUNDARY` refusal.
- Add the S30 contract test without mocks, stubs, patches, or locale-dependent prose assertions.
- Resolve the emitted `action_id` through production `lookup_action`; derive the target schema from that declaration and compare its canonical command key, live Click path, declaration bindings, and target input names.
- Validate the exact error outer spine, strict action wire DTO, and `ErrorEnvelope` model.
- Incorporate the initial review finding that a payload-derived target could mask catalogue drift, then obtain an independent PASS after remediation.

## Outcome

The real refusal proves a current `REFUSED_CLI_BOUNDARY` action chain from the rejected source leaf to the catalogue-declared target. The test validates the complete machine envelope: `schema_version`, `command`, `active_profile`, `status`, `error`, and `notices`; it rejects unmodelled error fields through `ErrorEnvelope` and validates the nested action as `ResolvedPreconditionAction` JSON.

The target comes exclusively from `lookup_action(action.action.action_id)`, not the emitted target key. Its emitted key and Click path agree with the declaration and its action binding names agree with both the declaration and the live input surface.

Verification passed: `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py` reported 30 passed; `ruff format --check` and `ruff check` passed; `basedpyright` reported zero errors, warnings, and notes; `git diff --check` passed.

## Notes

Marker boundary: S30 proves one registered root refusal reaches the canonical declaration and live input surface. It does not claim campaign-wide declared-observed closure or a successful recovery-and-retry journey.

The observed conditional `profile_name` recovery input and the wizard missing-input rejection are reassigned to amended S37. The retired error-registry-suggestion test reference is reassigned to amended S45. Those remain open campaign work rather than hidden S30 exclusions.

No Vault lifecycle state other than S30 is changed by this record.
