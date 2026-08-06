---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:20fc4b15dcfb0cda11a9c55dbb52cfcd1a38172247c3b87362ddcba13985e75f'
step_id: 'S30'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Run lint, typing, locale parity, command conformance, and docs/API scaffold checks for every touched live surface

## Scope

- `src/aeat docs dev/docs src/aeat/locales`

## Description

- Ran lint, typing, locale scaffold parity, documented-command conformance, and
  docs/API scaffold drift checks over the touched live surfaces and recorded the
  results.

## Outcome

All touched-live-surface quality gates are green at HEAD (2026-07-10).

Verification:

- Lint: `uv run --no-sync ruff check src/aeat/application/live src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_notifications_cli.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/_app_live_portals_cli.py src/aeat/entrypoints/cli/_app_live_verify_cli.py src/aeat/entrypoints/cli/_app_live_borrador_cli.py`
  -> `All checks passed!`.
- Typing: `uv run --no-sync ty check src/aeat/application/live` -> `All checks passed!`;
  `uv run --no-sync ty check` over the seven `_app_live*` CLI modules (incl.
  expedientes) -> `All checks passed!`.
- Locale parity: `uv run --no-sync python -m aeat.locales scaffold --check` ->
  `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, `hu.yml: ok`.
- Docs/API scaffold: `uv run --no-sync python -m dev.docs.apidocs scaffold --check`
  -> `Stub tree is conformant. No drift detected.`
- Command conformance: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q`
  -> `60 passed`.

## Notes

- Typing was run scoped to the touched live surfaces (`ty check` on the live
  application package and the live CLI modules) rather than the full-tree
  `dev.quality.types` wrapper, to avoid attributing unrelated peer diagnostics to
  this row per the full-tree-gate owner-distinction discipline. The scoped
  surfaces are clean.
