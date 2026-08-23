---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:04d2fb023c3c300232a987569e0978b9f6ddbb95d6adc227861d2ac439142ed8'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

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

### nested-group-failure-matrix-resolution | high | Resolved by exercising the complete matrix at both node kinds

Re-review confirmed that the real-module probe now selects either the parent
group loader or nested leaf loader as the failing node. Exact optional
dispatch, unclassified required dependency, same-namespace internal miss,
absent transitive dependency, ordinary `ImportError`, `SyntaxError`,
`RuntimeError`, required retry with original cause, and optional unavailable-
surface caching all run for both positions. Group resolution selects only the
parent token and continues to assert sibling exclusion; leaf resolution
selects the full parent/selected path. This closes the HIGH finding.

### optional-localization-boundary-resolution | medium | Resolved through a real lazy target and decorated dispatch

Re-review confirmed that every supported locale now writes and imports a real
temporary target module whose declared `playwright` dependency is blocked by
Python's meta-path protocol. The probe registers that module through
`LazyImportTarget` and `LazySubcommand`, applies the production optional and
required failure factories and shared decorator, then invokes both selected-
node help and dispatch through `CliRunner`. The localized surface is therefore
reached only after the lazy loader classifies and caches the exact optional
failure. The separate group/leaf cache cases prove one surface construction
per loader. This closes the MEDIUM finding.

The re-review reran the complete S12 integration file: 29 cases passed in real
subprocesses. Scoped Ruff and `ty` checks also passed. No HIGH or CRITICAL
finding remains open.

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
