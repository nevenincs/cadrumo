---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-13-missing-impl-audit-exec]]"
---

# aeat-restructure eliminate-shims: application / entrypoints / core audit

## status

Audit complete. Zero deletions required. The target lanes are clean.

## methodology

Ran all five hunt patterns (Grep-backed) across
`src/aeat/application/`, `src/aeat/entrypoints/`, and `src/aeat/core/`:

1. `^class (Fake|Stub|Dummy|Spy|Null|Mock|Shadow)\w*` — 0 hits
2. `raise NotImplementedError` — 0 hits
3. `^\s*\.\.\.\s*$` — 21 hits, all inside legitimate `Protocol` class methods or docstring examples
4. `^from \..* import \*` — 0 hits
5. `TYPE_CHECKING` blocks — 11 blocks found; every imported name verified as used in downstream annotations

## `...` body audit

All 21 `...` hits are Protocol method bodies (correct Python idiom) across:

- `src/aeat/application/setup/_protocols.py` — `Prompter`, `FirstRunRunner` (5 methods)
- `src/aeat/application/workflow/_protocols.py` — 6 Protocol classes (6 methods)
- `src/aeat/application/filing/_protocols.py` — `CasillaCollection.__iter__` (inline form, line 82)
- `src/aeat/application/sync/_protocols.py` — `CertificateBackend`, `LocalCatalogueLoader`, `SchemaLoader`, `ManualRulesLoader`, `LLMClient` (8 methods)
- `src/aeat/application/filing/__init__.py:48` — `...` inside a docstring code example (for-loop body), not a function

All Protocols have concrete implementers in `_adapters.py`, `_runner.py`, or `_prompter.py` — none are hollow.

## hollow-Protocol check

Every Protocol in the target lanes wires to at least one concrete implementer
in production adapters (`workflow/_adapters.py`, `sync/_runner.py`, `setup/_prompter.py`).
Zero hollow Protocols found.

## `_reset_for_tests` call-site check

Two production call sites found in `src/aeat/entrypoints/cli/security.py`
(lines 645, 690 — `KeyringMasterKeyProvider._reset_for_tests()` and
`FileFallbackMasterKeyProvider._reset_for_tests()`).

The definition in `src/aeat/adapters/persistence/storage/_master_key.py`
has NOT been renamed yet (Agent D pending). Call sites left as-is to avoid
breaking production; they will need updating to `_clear_cache` once Agent D
delivers the adapters-side rename.

## `testing.py` note

`src/aeat/application/filing/testing.py` exposes `SyntheticProfile`,
`SyntheticDeadlineStatus`, `SyntheticDeadlineChecker` — concrete
Protocol-conforming Pydantic models used by test files only. They do not
match any hunt-pattern prefix (Fake/Stub/Dummy/Mock/Shadow/Null/Spy)
and the mandate explicitly scopes to those names. Retained.

## verification gate

```
uv run pytest src/aeat/application/ src/aeat/entrypoints/ src/aeat/core/ -x -q
1213 passed, 5 skipped, 7 deselected in 198.86s
```

Collection errors in `src/aeat/adapters/` (124 errors) are pre-existing Agent B/D
scope — zero errors in target lanes.

## deletions

None. The target lanes had no stubs, fakes, hollow Protocols, re-export shims,
empty function bodies, or star-import shims to remove.
