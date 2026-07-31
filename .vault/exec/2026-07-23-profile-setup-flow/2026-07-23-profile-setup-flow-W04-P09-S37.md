---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:6719de0cf65bc8a594a3078c395eb06601d3e2615ffa2af576936fc120903cf5'
step_id: 'S37'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Add the AST gate asserting every tr(CONSTANT) call site's constant name carries the locale-key naming convention, closing the scanner-invisible-constant concealment class repo-wide

## Scope

- `src/cadrumo/locales/tests/`

## Description

- Ground first: `rg` confirmed the existing locale/translation AST-gate family
  (`test_dynamic_prefix_registry_coverage.py`, `test_locale_tr_positional_inventory.py`,
  `test_parity.py`'s own AST-scanner unit tests) and the canonical scanner
  module `locales/_ast_scanner.py` before writing anything, per the RAG
  discovery mandate — no duplicate scanning authority created.
- Extend `locales/_ast_scanner.py` rather than fork a second scanner: factor
  the `_LOCALE_KEY`/`_LOCALE_KEYS` suffix convention (previously inlined only
  inside `_declares_locale_key_constant`) into a shared
  `_LOCALE_KEY_CONSTANT_SUFFIXES` constant, then add
  `tr_constant_naming_violations_in_tree` (per-tree detector, reusing the
  existing `_translation_call_names` alias resolver so aliased `tr as _tr`
  imports are honoured identically to every sibling scanner) and
  `find_tr_constant_naming_violations` (public, root-walking entrypoint
  matching the signature shape of the two existing public functions
  `scan_source_tree`/`scan_namespace_markers`).
- Widen `_iter_parseable_python_modules` to yield `(path, tree)` pairs instead
  of bare trees so the new gate can report `path:line`, updating its two
  existing callers to unpack accordingly; behavior-preserving for both.
- Add `locales/tests/test_tr_constant_naming_convention.py`: one real
  repo-wide assertion (`find_tr_constant_naming_violations` over the live
  `src/cadrumo` tree returns empty) plus six non-tautological discrimination
  tests — the detector fires on a bare unsuffixed constant, fires through the
  aliased-import convention, stays clean on a correctly-suffixed constant, and
  correctly ignores a lowercase/dynamic argument, a literal string argument,
  and an unrelated non-`tr` callee.

## Outcome

Closes the fourth concealment-layer class the campaign's honesty themes
named: a `tr(CONSTANT)` call site whose constant lacks the
`_LOCALE_KEY`/`_LOCALE_KEYS` suffix was invisible to both existing AST
resolvers (the literal-argument scanner and the constant-declaration
scanner), so a missing catalogue entry or a typo on such a key raised
nothing. The gate is proven non-vacuous rather than trivially green: the one
live production site
(`REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY`, declared in
`application/wizard/_format_hints.py`, referenced from
`application/wizard/_registered_values.py`) is already compliant, so the
repo-wide assertion genuinely exercises the naming convention rather than
passing on an empty call-site set. Full verification: the new test file
(7/7 passing), the complete locale/translation suite across both marker
lanes (100/100: 93 unit + 7 integration), `ruff check`/`ruff format --check`
clean, and `pyright` 0 errors/warnings on both touched files.

## Notes

None.
