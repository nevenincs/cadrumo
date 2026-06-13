---
step_id: S205
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P09 S205-S212 — test-suite semantic intent audit

## Steps closed

S205, S206, S207, S208, S209, S210, S211, S212

## Enumeration results (S205 / S207 / S209 / S211)

**skip/xfail (S205):** 1 site — `src/aeat/core/observability/test_sink.py:380`
`@pytest.mark.skipif(sys.platform == "win32", ...)`.  Classified as legitimate
platform-conditional guard (POSIX chmod semantics unavailable to non-admin on
Windows).  Documented in `_DOCUMENTED_EXCEPTIONS` in `test_no_skip_xfail.py`.
Zero drift sites.

**mock imports (S207):** 0 sites.  No `unittest.mock` or `pytest_mock` imports
found under `src/aeat/`.  The codebase uses inline callables with
`monkeypatch.setattr` at the four boundary-injection points instead of the
mock library.

**monkeypatch.setattr (S209):** 4 documented boundary-injection sites:
- `test_browser_errors.py` (x2) — Playwright `default_browser_session_factory`
- `test_verify.py` (x1) — Playwright `default_browser_session_factory`
- `test_recovery_facade.py` (x1) — `decode_mnemonic` error path
- `test_config.py` (x2) — `_read_profile_record` CLI error boundary

All classified as legitimate (injecting behaviour at third-party transport /
OS-interface surfaces that cannot be exercised without live infra in unit
tests).  `sys.*` patches in `test_stdio.py` are unconditionally allowed
(process-global isolation).  Zero drift sites.

**tautological assertions (S211):** 0 true tautologies found.  The five
`assert var == var.lower()` shapes found by naive regex were confirmed as
non-tautological (right-hand side applies a transform).  `assert False, msg`
intentional-failure idiom also excluded.

## Artefacts produced

- `src/aeat/test_no_skip_xfail.py` — S205 + S206
- `src/aeat/test_mock_inventory.py` — S207 + S208
- `src/aeat/test_monkeypatch_inventory.py` — S209 + S210
- `src/aeat/test_no_tautology.py` — S211 + S212

## Quality gates

- 12/12 tests passing
- `ruff check` clean
- `pyright` 0 errors
- Marker integrity tests pass for all four new modules

## Commit

`3d2275e5b` — landed by peer agent sweep; files verified in git show output.
