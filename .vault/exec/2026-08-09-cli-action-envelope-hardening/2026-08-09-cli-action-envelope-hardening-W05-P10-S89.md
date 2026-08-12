---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6f27ef850ade5d26c812766f48d8cf4173dbfee2e7809ce90a57017f594045d3'
step_id: 'S89'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Complete the config CLI consumer fixed point by removing ad hoc recovery prose, English translation fallbacks, and exception-string flattening in favor of catalogue-backed messages, typed producer errors, canonical actions, or explicit no-recovery outcomes

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/locales/{ca,en,es,hu}.yml`

## Description

- Census every production config module for translation fallbacks, raw command guidance, raw notice messages, and exception text copied into messages, contexts, or result fields.
- Replace `config check` preflight `detail` and `remediation` prose with locale-neutral facts and invariant-checked typed action or no-recovery projections.
- Preserve typed application and adapter errors through the shared terminal boundary, or expose only stable error type/code facts when a result schema must record a failure.
- Resolve every emitted config translation key in Catalan, English, Spanish, and Hungarian through the locale authority.
- Keep shared S114 terminal rendering and S41 locale ownership boundaries intact.

## Outcome

- Exact discovered production-module paths, rather than a numeric floor, define the complete config conformance scope.
- Translation calls carry no source-language fallback, notices carry no raw literal message, and config outputs carry no exception string, validation message, or remediation prose copied from producers.
- `CheckPreflightPayload` carries `facts`, `precondition_action`, and `no_recovery_outcome`; unhealthy rows must carry exactly one action or closed outcome and healthy rows carry neither.
- `config check` intentionally drops the current S66 producer's `detail` and `remediation` strings and emits `operator_decision` until S66 supplies a typed precondition verdict and machine facts.
- Profile preflight, certificate, sandbox, bundle, Google, descendant, repair, readiness, and config-boundary paths now use catalogue messages, typed propagation, or stable error-type facts without raw exception text.
- Google failure projection delegates to the central exception registry rather than maintaining a config-local class-name map.
- S89 remains open for independent review.

## Verification

- Exact-scope conformance and real isolated multilingual `config check` JSON/text tests: 12 passed.
- Ruff check and formatting plus Python compilation pass for the complete config package.
- Locale-authority writes completed for `ca`, `en`, `es`, and `hu`; the global locale audit remains red only on unrelated concurrent Renta, IVA-wallet, modelo-work, and ledger catalogue drift.
- The broader certificate and sandbox real-CLI lane remains blocked before affected operations because its shared profile fixture omits the newly required `--tax-residence-jurisdiction-scope`; eight tests not dependent on that stale fixture pass and 57 stop at profile creation.

## Notes

- S66 must replace `PreflightCheck.detail` and `PreflightCheck.remediation` with typed machine facts and precondition verdicts. S89 does not infer actions from those strings and does not forward them.
- Tests use production source parsing, locale loading, CLI registration, and isolated storage; no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored business logic was introduced.
