---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:73b434a0fe967d871b02b16d6e82c0114dbe8f9e8004dbbf11179a6c7f86cd2a'
step_id: 'S89'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Complete the config CLI consumer fixed point by removing ad hoc recovery prose, English translation fallbacks, and exception-string flattening in favor of catalogue-backed messages, typed producer errors, canonical actions, or explicit no-recovery outcomes

## Scope

- `src/cadrumo/entrypoints/cli/_config`
- `src/cadrumo/locales/{ca,en,es,hu}.yml`

## Description

- Census every production config module for translation fallbacks, raw command guidance, raw notice messages, and flattened typed exceptions.
- Preserve application and adapter `CadrumoError` instances through the shared terminal boundary instead of reconstructing message-only CLI refusals.
- Remove certificate, profile-readiness, and sandbox command prose where no canonical executable action exists.
- Resolve every emitted config translation key in Catalan, English, Spanish, and Hungarian through the locale authority.
- Keep shared terminal rendering and locale catalogue ownership boundaries intact.

## Outcome

- All 46 production config modules are covered by a fixed-point AST conformance test.
- Translation calls carry no source-language `default` fallback, notices carry no raw literal message, and config refusal wrappers carry no `str(exc)` or `resolve_error_message(exc)` positional flattening.
- Profile preflight no longer publishes a hand-built modelo command, certificate output no longer publishes hand-built next actions, and sandbox merge refusals are catalogue-backed without command prose.
- Typed auth, certificate, custody, apoderado, and profile-bundle errors now propagate to the shared terminal boundary with their canonical error metadata intact.
- New config messages resolve in `ca`, `en`, `es`, and `hu` through locale-authority writes.
- S89 remains open for independent review.

## Verification

- `test_s89_action_conformance.py`: 3 passed.
- Ruff check and format plus Python compilation pass for the complete config package.
- The broader certificate and sandbox real-CLI lane is currently red before the affected operations: its shared profile fixture omits the newly required `--tax-residence-jurisdiction-scope` precondition. Eight tests which do not depend on that stale fixture pass; 57 stop at profile creation. This is an external fixture drift, not a green claim for the affected operations.

## Notes

- Tests use production AST parsing and production locale loading; no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored business logic was introduced.
- Shared S114 terminal rendering and S41 locale ownership were not reimplemented.
