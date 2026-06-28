---
step_id: "S01"
feature: upe-import-race
date: 2026-05-27
modified: '2026-05-27'
task: "#217"
tags:
  - "#exec"
  - "#upe-import-race"
related: []
---

# upe-import-race S01 — Deferred bind_error_code for circular-import window

## Intent

Task #217: `UnmatchedPlaceholderError` raises `ValueError` during CLI init in
concurrent subprocess environments. Root cause: `AeatError.__init_subclass__`
calls `bind_error_code(cls)` at class-creation time. When a stale pyc for
`registry/_core.py` causes `_DECLARED_CODE_BY_QUALNAME` to be absent (module
mid-initialization), the lookup raises `ValueError` before the class is
fully defined.

## Root cause

`errors/__init__.py` declares `CoreError(AeatError)` which triggers
`__init_subclass__` → `bind_error_code` → loads `_registry.py`. `_registry.py`
at module level does `from aeat.core.errors.registry import _ALL_DECLARED_ERROR_CODES`
(line 141) before `_DECLARED_CODE_BY_QUALNAME` is built (line 143). During
parallel-agent `__pycache__` write races, a subprocess that encounters a stale
pyc skips the source recompile and serves an incomplete module that never
reaches line 143. Any `AeatError` subclass defined in that window (including
`UnmatchedPlaceholderError` from `_render.py`) fires `__init_subclass__` against
the partial module and hits the `raise ValueError`.

## Fix

`src/aeat/core/errors/_registry.py`:
- Added `_DEFERRED_BIND: set[type[BaseException]]` — accumulates classes whose
  bind arrived before `_DECLARED_CODE_BY_QUALNAME` was populated
- `bind_error_code`: checks `globals().get("_DECLARED_CODE_BY_QUALNAME")` before
  accessing the mapping; silently adds to `_DEFERRED_BIND` and returns `None`
  when the mapping is absent (no raise at class-creation time)
- `_flush_deferred_binds()`: drains `_DEFERRED_BIND`; raises for classes that
  are still absent from the fully-populated mapping (genuine gaps, not races)
- `get_registered_error_code`: calls `_flush_deferred_binds()` before lookup,
  so deferred classes are bound at first runtime use

`src/aeat/core/errors/test_registry.py`:
- Added `test_deferred_bind_flushes_on_get_registered_error_code` — simulates
  the race by manually moving `UnmatchedPlaceholderError` into `_DEFERRED_BIND`,
  then verifying `_flush_deferred_binds()` rebinds it and
  `get_registered_error_code` returns the correct `ErrorCode`

## Verification

All 10 registry tests pass (including new regression test). All 11 i18n tests
pass. `test_registry_enforcement.py` continues to catch genuinely missing
entries via `_flush_deferred_binds()` called during `get_registered_error_code`.
