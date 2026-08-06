---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:9b53fbe3a525697603e5c0f30e0814224fe77322b7b7121398f010e607d1c49f'
step_id: 'S806'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Promote inline ReportLab Canvas constructions to module-scoped fixtures

## Scope

- `src/aeat/adapters/inbound/borrador/tests/test_modelo_100_summary.py`

## Description

- Ground the five plan-named targets against HEAD; the test-topology refactor
  renamed or split four of them and the fifth was already migrated.
- Confirm `test_parser.py` (justificante) already carries module-scoped path
  fixtures plus a module-scoped Canvas bytes fixture; no change needed.
- Confirm `test_record_design.py`, the sede `_declarations_support` builder,
  and the declaracion `_parser_boundary_support` builder each render per-test
  varying PDF content (per-modelo, per-value, per-artefact-kind); those are
  genuinely per-test and not promotable without changing test semantics.
- In the borrador summary tests, extract a pure `_render_borrador_pdf_bytes`
  builder and a `_write_borrador_pdf` writer from the old per-test
  `_generate_pdf`.
- Add a module-scoped `default_borrador_pdf_bytes` fixture that renders the
  shared default BORRADOR artefact once per module.
- Route the six default-content tests through the fixture, each writing the
  cached bytes into its own `tmp_path` file so rename and isolation semantics
  are preserved; leave the content-varying tests on the refactored
  `_generate_pdf`.

## Outcome

- 18 tests in the borrador summary module pass. The default BORRADOR Canvas
  build collapses from six constructions to one per module.
- Behaviour preserved: a mutation probe that rendered the shared fixture as
  PREDECLARACION content made `test_detects_borrador` fail, confirming the
  tests still depend on the real BORRADOR bytes and the fixture change is not
  tautological.
- Ruff clean.

## Notes

- Post-refactor reality: only the justificante file had per-module-deterministic
  PDFs and it was already migrated, so the substantive remaining promotion was
  the borrador default-content subset. The other three targets build per-test
  varying PDFs and were intentionally left; forcing a shared fixture onto them
  would either break per-test isolation or weaken the assertions.
- The secure-storage autouse fixture hosted in the sede `_declarations_support`
  module was not touched (deferred S804 surface).
