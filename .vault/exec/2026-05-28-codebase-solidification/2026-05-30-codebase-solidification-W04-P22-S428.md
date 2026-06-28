---
step_id: "W04.P22.S428"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta8
commit: e7f96f6ec
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# W04.P22.S428 — Aggregate real-behavior test

Created `src/aeat/test_w04_p22_cleanup.py` with 11 real-behavior assertions:

- (a) `_setup_answers.py` cannot be imported — `importlib.util.find_spec` returns None
- (a) `SetupAnswers.__module__` is `"aeat.core.profile"`
- (b) `CounterpartSourceKind` defined in domain `_bindings` module
- (b) Application `_counterpart.CounterpartSourceKind is domain._bindings.CounterpartSourceKind`
- (c) `_notifications._parse_date_local` delegates correctly (valid date + None on error)
- (c) `_censo._parse_date` source contains `_parse_date_canonical`
- (c) `_profiles._parse_date` source contains `_parse_date_canonical`
- (d) `ApoderadoService` importable; CLI entrypoint contains `"ApoderadoService"`
- (e) Missing `verification_source` raises `TypeError` at class definition
- (e) `no_corpus` + `provisional_pending_specimen=False` raises `TypeError`
- (e) Compliant provider class defined without error

All 11 tests pass. No mocks, no skips, no xfail.

**Files touched:** `src/aeat/test_w04_p22_cleanup.py` (created)
