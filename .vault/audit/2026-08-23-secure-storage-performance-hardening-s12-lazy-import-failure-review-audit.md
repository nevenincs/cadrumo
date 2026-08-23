---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:74c90de1c7e31649445b4a6d94f841354665623addebaf37a08711278dbb7e53'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-performance-hardening` audit: `S12 nested lazy import failure review`

## Scope

Independent review of `W02.P03.S12` against the accepted command-scoped
loading decision, the S09--S11 execution records, and the delegated failure
matrix. The review inspected the current changes in
`test_nested_lazy_import_failures.py` and `_command_group_import_support.py`
and reran all 20 S12 integration cases in real subprocesses, plus scoped Ruff
and `ty` checks. The audit focused on nested group and leaf loading, exact
optional classification, fail-loud internal and transitive failures, non-
`ModuleNotFoundError` defects, metadata-only help/completion, selected-path
dispatch, retry/cache behavior, localization, sibling exclusion, and cause
preservation.

## Findings

### nested-group-failure-matrix | high | The new real-import matrix exercises failures only at the leaf loader

The temporary package always gives `parent` a healthy module and injects every
exact-optional, same-namespace internal, transitive, non-module `ImportError`,
syntax, and runtime defect into `selected`. Root and parent help/completion
therefore prove metadata traversal, but do not execute a failing nested-group
loader. The pre-existing real `app modelo --help` case covers one missing
required package at a nested group; it does not cover exact optional,
same-namespace internal/transitive `ModuleNotFoundError`, non-module
`ImportError`, syntax/runtime failure, dispatch, or repeated/cache semantics at
that node kind. Consequently the explicit S12 promise to extend failure
coverage across nested groups **and** leaves is only partially proven. A
regression that applies different classification or caching while loading a
group could pass the current suite.

### optional-localization-boundary | medium | Localized optional coverage bypasses the lazy-import classifier

`_OPTIONAL_LOCALE_PROBE` constructs a `ModuleNotFoundError` and calls
`_surface_for_import_failure` directly. It proves localization of an already
chosen unavailable surface, while the synthetic lazy-loader dispatch uses a
custom English-only callback. No localized real-process case therefore proves
that an exact declared optional failure raised by importing a selected lazy
node is classified, materialized, decorated, and dispatched through the shared
operator envelope. The required branch does exercise the installed CLI end to
end, so the asymmetry can conceal a wiring regression unique to optional lazy
targets.

## Recommendations

- For `nested-group-failure-matrix`, parameterize the same real temporary-
  module probe by failing node kind. Give the parent loader the same exact
  optional, internal/transitive, non-`ModuleNotFoundError`, syntax/runtime,
  retry, and optional-cache cases already applied to the leaf, and exercise
  parent resolution/dispatch while continuing to assert that its child and
  sibling modules remain absent. Do not satisfy this with a direct classifier
  call or mocked importer.
- For `optional-localization-boundary`, drive a declared optional miss through
  `LazySubcommand.load()` and the decorated real CLI runner in every supported
  locale. Assert localized help and refusal, registered exit/error identity,
  exact dependency context, absence of `No such command` and traceback text,
  and single cached unavailable-surface construction. Retain the current
  direct surface test only as lower-level complementary evidence.
