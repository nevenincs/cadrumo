---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S190'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W08.P36.S190`

Fixed `_generate.py` PDF metadata non-determinism by passing `invariant=True`
to every `canvas.Canvas(...)` call. Regenerated all 18 fixture PDFs with
deterministic metadata. Eliminates fixture-regen sweep churn going forward.

- Modified: `src/aeat/tests/fixtures/justificantes/_generate.py`
- Regenerated: 18 fixture PDFs under `src/aeat/tests/fixtures/justificantes/`
- Commit: `a04be5ff2`

## Description

**Root cause**: reportlab's `Canvas` stamped `/CreationDate` and `/ModDate`
with the current wall-clock timestamp on every `save()` call. The existing
`setProducer("reportlab")` call was overriding the user value back to
reportlab's version string in some reportlab versions. Different sessions
produced different PDF bytes even when no content changed.

**Fix**: `canvas.Canvas(..., invariant=True)` activates reportlab's built-in
reproducible-output mode. It pins `/CreationDate` and `/ModDate` to
`D:20000101000000+00'00'` (the reportlab epoch, `946684800.0`) and
preserves the explicit `setProducer()` value. The `setProducer()` calls
were also updated from `"reportlab"` to `"aeat-test-fixture-generator"` to
make the source of the fixture explicit.

The fix was verified by running the generator twice in succession and
confirming `git diff -- src/aeat/tests/fixtures/justificantes/` produces
zero PDF changes after the second run.

## Tests

99/99 tests in `test_parser_boundary.py` pass against the regenerated
fixtures. The round-trip parse results are identical because `invariant=True`
only affects PDF metadata fields — the rendered page content is unchanged.
