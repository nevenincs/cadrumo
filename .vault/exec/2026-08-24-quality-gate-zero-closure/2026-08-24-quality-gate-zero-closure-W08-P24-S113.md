---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:61951436746a926875ef8515b6af96d20cf27aaf83e5538384abcd2e208b5f5a'
step_id: 'S113'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Land the detector gates under dev/quality/tests/, which the per-push test-dev-ci path set already invokes, adding no lane and touching no workflow file so ci-lane-deconflation keeps sole ownership of that surface, and prove the existing lane runs them (Luna max audit and mechanical)

## Scope

- `dev/quality/tests/`
- `dev/tests/test_tautological_assertion_gate.py`

## Changes

- Retired the old off-lane tautological-assertion gate after its strengthened replacement landed under `dev/quality/tests/`.
- Kept all three structural detector gates marked `unit`, matching the first existing `test-dev-ci` marker expression.
- Added no lane and changed neither `justfile` nor `.github/workflows/`.

## Verification

- `just --dry-run test-dev-ci` shows the existing first command selects `unit or (integration and not serial)` and includes `dev/quality/tests`; its second command also includes that path for serial integration tests.
- `.github/workflows/ci.yml` already invokes `just test-dev-ci` in the per-push tooling and workflow conformance job.
- `uv run --no-sync pytest --collect-only -q -n 0 -m "unit or (integration and not serial)" dev/quality/tests/test_tautological_assertion_gate.py dev/quality/tests/test_subsuming_disjunctions.py dev/quality/tests/test_self_echoing_tokens.py` -> `79 tests collected`; no detector-gate case was deselected.
- The same three files executed under their normal focused run in S112: `79 passed`.
