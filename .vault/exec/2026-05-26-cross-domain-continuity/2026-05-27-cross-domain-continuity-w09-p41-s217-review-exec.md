---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09-P41 S217 Code Review

Commit: `323fbc6b4` — `#217 bind_error_code: defer binding when _DECLARED_CODE_BY_QUALNAME not yet populated`

Files changed: `src/aeat/core/errors/_registry.py`, `src/aeat/core/errors/test_registry.py`

---

## Status: APPROVE

No CRITICAL or HIGH issues. One MEDIUM finding (deferred-class silent failure path), one LOW finding (type-ignore on return). Safe to merge.

---

## Critical Question Answers

**Q1 — Fix approach:**
Lazy defer, not import-order reordering. `bind_error_code` now guards with `globals().get("_DECLARED_CODE_BY_QUALNAME")`. When the name is absent during the circular-import window the class is inserted into `_DEFERRED_BIND` instead of raising. `get_registered_error_code` calls `_flush_deferred_binds()` on every invocation, draining the set at first runtime use. Class creation time is no longer the enforcement point.

**Q2 — Backward compatibility:**
Preserved. All currently-registered subclasses remain in `_CLASS_CODE_REGISTRY` because `bind_error_code` returns early when `_CLASS_CODE_REGISTRY.get(error_type)` is not `None`. `_flush_deferred_binds` reuses the same `_DECLARED_CODE_BY_QUALNAME` and calls `type.__setattr__` to restore the `code` class variable. No regression path for the dozens of registered subclasses.

**Q3 — Regression test quality:**
The test `test_deferred_bind_flushes_on_get_registered_error_code` simulates the race by manually evicting `UnmatchedPlaceholderError` from `_CLASS_CODE_REGISTRY`, adding it to `_DEFERRED_BIND`, then verifying `_flush_deferred_binds()` rebinds it. The `finally` block restores the invariant. This exercises the real mechanism without mocking, which is compliant with the no-mock gate. However it does not exercise a genuine fresh-subprocess / stale-pyc import race; that would require a `subprocess` call with `--import-mode=importlib` and a cleared `__pycache__`. This is a structural simulation, not a true import-order integration test (see MEDIUM-001).

**Q4 — Strict mode:**
No `corpus_strict` or equivalent dev/test enforcement of eager binding is present or was removed. There is no strict-mode concept in the original code either; `test_registry_enforcement.py` serves as the static gate: it imports every module in the `aeat` package then calls `get_registered_error_code` on every discovered subclass, which will now trigger `_flush_deferred_binds()` and raise `ValueError` for any class genuinely absent from `_DECLARED_CODE_BY_QUALNAME`. Enforcement is runtime-deferred but the CI test walks all subclasses after full import so the net guarantee is the same.

**Q5 — Rendering paths unaffected:**
`build_error_envelope`, `render_error_text`, and `render_error_json` all call `get_registered_error_code`, which now prefixes with `_flush_deferred_binds()`. `UnmatchedPlaceholderError` and all other `CoreError` subclasses reach `get_registered_error_code` at raise time, by which point all modules are fully imported and `_DEFERRED_BIND` would have been populated at worst during module init and flushed here. No regression.

**Q6 — Anti-tautology:**
The test pops the class from `_CLASS_CODE_REGISTRY` so a trivial early-return cannot hide a broken flush. It then asserts both the absence from `_DEFERRED_BIND` and the presence in `_CLASS_CODE_REGISTRY` after `_flush_deferred_binds()`, then independently confirms the code string via `get_registered_error_code`. The intermediate-state assertions are meaningful. The `finally` block does not suppress assertion failures (uses `try/finally`, not `try/except`). Anti-tautology criterion is met.

**Q7 — Documentation:**
Module-level comment on `_DEFERRED_BIND` (lines 120-125) explains the circular-import window. Docstring on `bind_error_code` explains the deferral contract. Docstring on `_flush_deferred_binds` explains when it is called. Docstring on `get_registered_error_code` explains the drain semantics. Coverage is adequate.

---

## Findings

### SAFETY-001 | MEDIUM | Silent still_pending accumulation in `_flush_deferred_binds`

If a deferred class resolves to `None` in `_DECLARED_CODE_BY_QUALNAME` it is silently moved to `still_pending` and re-added to `_DEFERRED_BIND`. Because `_flush_deferred_binds` is called on every `get_registered_error_code` invocation, a genuinely missing class will cause an O(n) re-scan of `_DEFERRED_BIND` on every error lookup for the lifetime of the process. More critically, the missing entry will never raise until `bind_error_code` is reached via the fallback path at line 233. The call chain `get_registered_error_code` → `_flush_deferred_binds` (class stays pending) → `code = _CLASS_CODE_REGISTRY.get(error_type)` returns `None` → `bind_error_code(error_type)` → NOW raises `ValueError`. This delayed raise is correct at the end but the silent re-queue without an early warning means a missing entry only surfaces when the specific error is instantiated at runtime, not at the `_flush_deferred_binds` call. For test environments this is fine because `test_registry_enforcement.py` exercises every subclass. In production, a misconfigured class would crash at the raise site rather than at startup. The `test_registry_enforcement` gate closes the gap for CI but the defensive posture of `_flush_deferred_binds` silently re-queuing rather than raising (since `_DECLARED_CODE_BY_QUALNAME` is provably populated at that point) is mildly unsafe. A comment clarifying why `still_pending` is tolerated (i.e. only possible during module re-import scenarios that the enforcement test will catch) would harden the reasoning.

Severity: MEDIUM. Not a crash path; enforcement gate catches it in CI. No fix required before merge.

### STYLE-001 | LOW | `type: ignore[return-value]` on deferred return

`bind_error_code` at line 210 returns `None` with `# type: ignore[return-value]` when deferring. The return type annotation is `ErrorCode`. Callers in `__init_subclass__` discard the return value so this is not a runtime hazard, but the ignore comment papers over a real type inconsistency. A cleaner signature would be `ErrorCode | None` with callers adapting, or the deferred path could raise `RuntimeError` for the not-yet-available state (relying entirely on `get_registered_error_code` for the lazy lookup). This is cosmetic but may confuse a future maintainer.

Severity: LOW. No action required.

---

## Standing Gate Results

- G1 (no naked env reads): No `os.environ`/`os.getenv` introduced. Pass.
- G2 (typed pydantic at boundaries): `ErrorCode` and `ErrorEnvelope` remain `BaseModel` with `strict=True`. No new bare dict boundaries. Pass.
- G3 (tr() for user messages): No new user-facing message strings added. `render_error_text` path unchanged. Pass.
- G4 (locale via scaffold+audit): No locale YML changes. Pass.
- G5 (no shims/duplication): Change introduces no compatibility layer or re-export. `_DEFERRED_BIND` + `_flush_deferred_binds` are a coherent addition to the existing registry module, not a parallel implementation. Pass.
- G6 (no tautological tests): Test pops the real registry entry and verifies the flush independently. Genuine behavior under test. Pass.
