---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:86bcc6c7704fca925a3276a9effaed7d2f7e081502a3572228b07e3ceee8fa16'
step_id: 'S121'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Give the verdict-grammar detector a gate carrying a positive control that fires on the repaired report.py shape and an anti-vacuity floor that fails when the swept verdict-consumer population collapses, and kill that gate with mutmut under the standing scope (Luna max audit and mechanical)

## Scope

- `dev/quality/tests/`

## Changes

- `A` `dev/quality/tests/fixtures/gate_verdict_clean.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_binding_edges.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_direct_output.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_foreign_run.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_future_output.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_non_name_binding.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_overwritten_output.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_second_literal.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_source_order_edges.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_unenrolled.py.fixture`
- `A` `dev/quality/tests/fixtures/gate_verdict_weak.py.fixture`
- `A` `dev/quality/tests/test_gate_verdict_grammar.py`
- `M` `pyproject.toml`
- `verify:` `uv run pytest dev/quality/tests/test_gate_verdict_grammar.py -q` -> `pass` (`12 passed`)
- `verify:` `uv run ruff check dev/quality/gate_verdict_grammar.py dev/quality/tests/test_gate_verdict_grammar.py` -> `pass`
- `verify:` `uv run basedpyright dev/quality/gate_verdict_grammar.py dev/quality/tests/test_gate_verdict_grammar.py` -> `pass` (`0 errors, 0 warnings, 0 notes`)
- `verify:` `/tmp/cadrumo-mutmut-venv/bin/mutmut run` in the dedicated native isolate, followed by a focused current-control recheck -> `pass` (`445 selected; 421 killed; 24 inert survivors`)

## Notes

The clean final-byte run selected 445 mutants and killed 419. Source-order
controls for same-line assignments then killed the two actionable survivors
that removed `col_offset`, producing 421 killed mutants. The 24 remaining
survivors were inspected individually and are inert: six change only parser
diagnostic filenames or the equivalent `UTF-8` codec spelling; two replace
`zip(..., strict=False)` with equivalent non-strict forms; the `_position`
survivors alter fallback values that positioned parsed AST nodes never use;
and the remaining provenance survivors change recursion/order branches that
cannot be reached or distinguished under the detector's preceding-assignment
and parsed-position invariants. The suite explicitly exercises future writes,
overwrites, direct subprocess output, helper propagation, cyclic/self aliases,
and same-line source order. No aggregate mutation metric was calculated or
reported.
