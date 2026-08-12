---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5082f1d451ed3b0727815bb8fc19b8a9f1c1e65041197ce4d49f048dcb5cdda8'
step_id: 'S33'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Centralise binding-source readiness wording

## Scope

- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`
- The four locale catalogues and direct readiness projection and CLI tests

## Description

- Delete the entrypoint-owned readiness dictionary and fallback helper.
- Define the immutable, Spanish-named `CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS` mapping beside the existing application readiness action projections.
- Use the repository's `_LOCALE_KEYS` naming contract so the locale AST scanner discovers the same literal values that the runtime mapping owns.
- Key the mapping by every `BindingSourceKind` member and assert exact set equality at import time.
- Make CLI list and resolve paths index the typed mapping and translate its locale key without a default or unknown-source fallback.
- Author the readiness leaves in Catalan, English, Spanish, and Hungarian through `dev.locales set-batch`.

## Outcome

The entrypoint no longer owns readiness semantics. The application layer exposes one immutable total projection from the native binding-source enum to localized operator wording. Semantically identical ledger-backed sources deliberately share one locale key; distinct sources retain distinct nouns. Unknown and newly added enum members fail closed rather than being laundered as ledger data.

Verification:

- direct action/readiness projection tests: 9 passed serially;
- real Spanish `bindings list` and `bindings resolve` integration regression: 1 passed serially, proving relation-prefill and ledger-backed sources render distinct localized nouns;
- Ruff check and format check over the changed Python surface: passed;
- strict BasedPyright over the application owner and direct test: zero errors, warnings, or notes;
- every projected key resolves in all four catalogues and the mapping rejects mutation;
- locale scaffold no longer reports any `cli.app.modelo.bindings.readiness.*` leaf as missing or extra; the command remains red only on unrelated profile-schema, IVA-wallet, retired-verification, dependency-help, and ledger catalogue drift;
- scoped `git diff --check`: passed.

## Notes

The locale batch was applied through the catalogue authority after an earlier interrupted partial batch. No compatibility helper, fallback, alias, or mirrored business mapping remains.

Concurrent shared-worktree commits split the Step delivery: `954fb76297` landed the code, tests, and four catalogue changes; `25c101ee57` landed this execution record alongside unrelated S114 lifecycle work. This violates the plan's one-Step/one-atomic-commit convention. Shared history is not rewritten; the final S33 closure is limited to this factual correction, the formal review audit, and the plan checkbox.
