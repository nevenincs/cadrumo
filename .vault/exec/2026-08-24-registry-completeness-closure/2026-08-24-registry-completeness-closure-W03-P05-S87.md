---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a0ab70e81d104d906ebeae49023d74b8fde7723e84ae8faf8a07c96a1edcf00d'
step_id: 'S87'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Cut the registry closure CLI over from the disabled single-channel proof port to the canonical two-channel assessment, preserving typed per-channel refusals and public receipt secrecy, and prove an eligible two-receipt assessment can satisfy the filing-export limb without a second writer or payload digest projection

## Scope

- `src/cadrumo/application/registry/`
- `src/cadrumo/application/filing/`
- `dev/registry/conformance/`
- `dev/registry/`
- `src/cadrumo/application/registry/tests/`
- `dev/registry/conformance/tests/`

## Description

- Reopen S87 through the canonical plan command after independent audit `a045625050` found two medium two-channel cutover gaps.
- Resolve one current assessment instant per generic filing-export coverage report and refuse complete proof assessments whose secure-replay receipt is expired or not yet current.
- Preserve the typed public refusal as `secure_replay:proof_validation_failed` without projecting the receipt into satisfied evidence.
- Map the canonical encrypted custody `PersistenceError` family, including `SecretStoreError`, to the bounded `secure_replay:custody_failed` refusal.
- Add mutation-sensitive focused application and development-authority tests for expired receipt injection and configured encrypted-custody failure.

## Outcome

Registry closure eligibility now requires a secure-replay receipt to be current at the report's injected or canonical assessment instant, even when a substitute authority returns an otherwise complete typed proof. Configured encrypted custody failures in the governed persistence family fail closed as a typed secure-replay custody refusal, without exposing the storage exception detail. The two mandatory receipt channels, the sole canonical writer, and public receipt secrecy remain intact.

## Notes

Remediation provenance: independent audit `2026-08-26-registry-completeness-closure-s87-two-channel-cutover-review-audit` (`a045625050`), findings `replay-receipt-freshness` and `secure-custody-refusal-mapping`.

Focused review of the exact S87 diff against the accepted two-channel export-proof ADR found no high or critical issue. Scoped checks passed: exact-path Ruff; the isolated application expiry regression; and both `PersistenceError` and `SecretStoreError` custody-refusal cases in the development authority. No Modelo 200 registry data or unrelated in-flight changes were altered or staged by this Step.
