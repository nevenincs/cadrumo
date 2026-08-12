---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:bfc0f16ee156f464c64933e12a4597d91bc0a2980e28767ef603cd71f37f4e5e'
step_id: 'S89'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Complete the config CLI consumer fixed point by removing ad hoc recovery prose, English translation fallbacks, and exception-string flattening in favor of catalogue-backed messages, typed producer errors, canonical actions, or explicit no-recovery outcomes

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/locales/{ca,en,es,hu}.yml`
- Shared producer dependency: S66 application preflight contract

## Description

- Census every production config module for translation fallbacks, raw command guidance, raw notice messages, and exception text copied into messages, contexts, or result fields.
- Preserve S66 preflight facts and exact typed action or no-recovery verdicts through the config-check payload and renderer.
- Preserve typed application and adapter errors through the shared terminal boundary, or expose only stable error type/code facts when a result schema must record a failure.
- Resolve every emitted config translation key in Catalan, English, Spanish, and Hungarian through the locale authority.
- Keep shared S114 terminal rendering and S41 locale ownership boundaries intact.

## Outcome

- Exact discovered production-module paths, rather than a numeric floor, define the complete config conformance scope.
- Translation calls carry no source-language fallback, notices carry no raw literal message, and config outputs carry no exception string, validation message, or remediation prose copied from producers.
- `CheckPreflightPayload` carries `facts` and one resolved `precondition_action`; unhealthy rows preserve exactly the producer's canonical action or closed outcome and healthy rows carry neither.
- `config check` no longer drops S66 producer state or invents `operator_decision`; it losslessly resolves the producer-owned typed verdict.
- Profile preflight, certificate, sandbox, bundle, Google, descendant, repair, readiness, and config-boundary paths use catalogue messages, typed propagation, or stable error-type facts without raw exception text.
- Google failure projection delegates to the central exception registry rather than maintaining a config-local class-name map.
- S89 remains open for independent review.

## Verification

- Existing exact-scope config conformance campaign: 45 passed.
- S66 dependency application preflight unit tests: 18 passed.
- Config-check integration and all-locale action conformance tests after the S66 cutover: 12 passed.
- Ruff check, Ruff formatting, and Python compilation pass for the shared S66/S89 surface.

## Notes

- S66 now supplies typed machine facts and precondition verdicts. S89 preserves them without action inference, compatibility fields, or locale-specific producer content.
- Tests use production source parsing, locale loading, CLI registration, and isolated storage; no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored business logic was introduced.

## Coordinated canonical rehoming reconciliation

A fresh read-only derivation established three identical stability boundaries separated by at least sixty seconds. Immediately before mutation, the canonical guard revalidated the ledger, plan, all-source, rendered postimage, structural-delta, and locator-delta hashes byte-for-byte. OWNER_ZERO was zero and every one of the twenty-four structural additions had exactly one open owner. The delta contained thirty-five removals, no historical-row, disposition, or current-identity changes, and 144 locator-only refreshes recorded as incidental metadata.

Exactly one S50 canonical-tool write produced the proven postimage. The resulting ledger SHA-256 is `bc6ddc3b5edddd852a155e48ca58ec6e3aa188f716cecef8615b9bef20de2aec`. Direct validation returned `E_REHOMING_VALIDATED:238`; the single immediate no-write replay returned `E_REHOMING_MIGRATION_CHECKED:238`. No second locator chase or write was performed. The complete canonical rehoming lane passed 74 tests.

This owner Step remains open for independent review and ledger reconciliation.
