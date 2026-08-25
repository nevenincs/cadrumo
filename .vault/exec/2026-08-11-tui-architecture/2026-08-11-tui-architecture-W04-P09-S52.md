---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c05d1c668e0ac88a73a89ceea1059d5fa7076862f0980c3915a84c38b3261a01'
step_id: 'S52'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement safe error and bounded log renderers without accepting raw exceptions or retaining lifecycle authority

## Scope

- `src/cadrumo/entrypoints/tui/components`

## Description

- Add canonical inert error and log components with a shared safe-text boundary.
- Render only bounded display facts from a canonical `ErrorEnvelope`; omit envelope context, action, and diagnostic identifiers.
- Accept only typed safe log records and retain a fixed tail without subscriptions, retention, workers, or lifecycle ownership.
- Refuse raw exceptions and unsafe traceback, URL, path, credential, token, identity, multiline, and escape-bearing text before it reaches a widget.
- Add adversarial and Textual tests for redaction preconditions, visible elision, bounded retention, and opaque canonical projections.

## Outcome

The canonical `components.errors` and `components.logs` modules now own only display mechanics. The error panel accepts `ErrorEnvelope` rather than an exception and projects only its closed category, stable code, and pre-redacted message. The log panel accepts only local `SafeLogRecord` values and retains a fixed tail. Both routes use the core redactor only as a precondition check, never to classify a failure or construct diagnostic policy.

Commit `606d2ea954` (`feat(tui): add safe error and log presentation`) contains the five implementation and test files. Independent review approved the completed step.

Verification passed: component Textual/unit suite (24 tests), dedicated adversarial error/log suite (16 tests), scoped collection (24 tests), Ruff check and format, ty, direct-import/legacy/authority censuses, and scoped diff check.

## Notes

The shared import-hygiene gate remains red for unrelated test-debt drift: it measured 55 current private-import sites against 44 documented sites before the component-specific checks. S52 introduces none of those private imports and did not alter the shared debt ledger.
