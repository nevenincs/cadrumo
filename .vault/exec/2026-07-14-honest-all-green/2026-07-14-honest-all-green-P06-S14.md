---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S14'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Complete the landed CLI-identity rename's locale sweep so codebase-to-locale parity and the two locale-audit tests are green

## Scope

- `src/cadrumo/locales`

## Description

- Confirmed the locale-identity campaign was not mid-landing: no uncommitted WIP on `src/cadrumo/locales`, the parity/audit test files, or `entrypoints/cli/__init__.py` (the CLI-identity underscore rename was already committed).
- Re-ran the three failing tests sequentially at HEAD: `test_codebase_to_locale_parity` (26 orphan `cli.help.*`/`cli.root.*` keys), `test_committed_catalogues_pass_production_audit` (same 26), and `test_committed_catalogues_follow_contextual_product_identity_contract` (an extra `errors.auth.auth_former_product_session_state` key).
- Root-caused the 26 orphans: NOT dead keys. The CLI-identity rename aliased the translator import module-level (`from cadrumo.core.i18n import tr as _tr`) at 5 sites (chiefly `entrypoints/cli/__init__.py`); the AST locale-key scanner (`locales/_ast_scanner.py`) only recognised calls literally named `tr`/`t`, so every `_tr(\"...\")` call was invisible and its live catalogue key was mis-reported as an orphan. Verified each stem is genuinely consumed via `_tr` in the committed codebase (e.g. `cli.root.verbose_help` in `__init__.py:136`), so scaffolding them away would have deleted live keys and broken CLI help.
- Fixed the scanner to resolve per-module `tr`/`t` import aliases and treat the aliased local name as a translation call in both the concrete-key (`_collect_call_site_keys`) and concat-prefix (`_extract_concat_prefixes`) walkers. Added two regression tests (alias resolution + anti-vacuity: a same-named local function that is not a `tr` alias is ignored).
- Diagnosed the identity-contract failure: `errors.auth.auth_former_product_session_state` is a legitimately-added, live key (a Cadrumo-prose message about a retired-product AEAT session, consumed in `core/errors/registry/_adapters_part2.py`) with `Cadrumo` prose in all four locales; the contract's `_PROSE_KEYS` expectation simply had not been updated for it. Enrolled the key in `_PROSE_KEYS` for en/es/ca/hu.

## Outcome

Every S14 gate green, no `.yml` hand-edit and no key deletion: `test_codebase_to_locale_parity`, both locale-audit tests (`test_committed_catalogues_pass_production_audit`, `test_committed_catalogues_follow_contextual_product_identity_contract`), the translation-honesty gate, and `python -m cadrumo.locales scaffold --check` (all four catalogues `ok`). Full parity + audit suites: 43 passed. Commit `d487eb9781`, explicit pathspec.

## Notes

The fix was in the scanner and the test expectations, never the catalogues - the keys were live all along, so the prescribed "scaffold to remove orphans" path would have been wrong (it would have pruned live `_tr` keys and broken CLI help; scaffold uses the same scanner, so it now correctly keeps them). This is the "fix the scanner rather than silently skipping" principle the parity module itself states. `scaffold --check` must be run with a clean `CADRUMO_LOCAL_STORAGE_ROOT` (the ambient dev storage root carries an `aeat.db` that trips the former-product-database refusal on CLI startup - an environment condition, not a locale issue; the pytest gates isolate storage and are unaffected). No destructive git operations; peer-staged index files were left untouched by the explicit-pathspec commit.
