---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S81
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W02.P07 — auth and bucket verb payload classes

## Outcome

Extended `_config_payloads.py` with eight auth/bucket verb `OutputSchema` subclasses: `AuthProvidersResult`, `AuthConfigureResult`, `AuthStatusResult`, `AuthTestResult`, `AuthLoginResult`, `AuthClearResult`, `ApoderadoCheckResult`, `BucketHistoryResult`.

`AuthStatusResult`, `AuthTestResult`, and `AuthLoginResult` use `model_config = ConfigDict(extra="allow")` so application-layer model dumps pass through without re-declaring every provider-specific field. These use `model_validate(payload)` at the call site to avoid strict-mode type coercion issues.

`AuthConfigureResult` wraps the application result fields explicitly; the local variable was renamed `configure_result` to avoid shadowing the `result` binding from the `configure_operator_auth` call.

`BucketHistoryResult` wraps the `_bucket_history_event_payload` helper output in a `list[dict[str, object]]` events field.

Migrated 8 bare emit sites: auth.providers, auth.configure, auth.status, auth.test, auth.login, auth.clear, apoderado.check, bucket.history.

## Files changed

- `src/aeat/entrypoints/cli/_config_payloads.py` — 8 schema classes added (S66, S68, S70, S72, S74, S76, S78, S80)
- `src/aeat/entrypoints/cli/_config/__init__.py` — 8 auth/bucket emit sites migrated (S67, S69, S71, S73, S75, S77, S79, S81)

## Gate

Conformance gate passes for all 8 auth/bucket paths. 103 config tests pass.
