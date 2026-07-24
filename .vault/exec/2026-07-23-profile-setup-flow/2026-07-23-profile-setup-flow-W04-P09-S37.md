---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S37'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S37 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the AST gate asserting every tr(CONSTANT) call site's constant name carries the locale-key naming convention, closing the scanner-invisible-constant concealment class repo-wide and ## Scope

- `src/cadrumo/locales/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
