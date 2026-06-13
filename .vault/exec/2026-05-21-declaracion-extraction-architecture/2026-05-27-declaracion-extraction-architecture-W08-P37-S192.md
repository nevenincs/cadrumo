---
step_id: S192
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P37.S192 — restructure M130/M131 gap tests to assert on typed exception attributes

## Outcome

Commit `e2de32c62`. 17/17 gap tests pass.

## Actions

`DeclaracionParseError` previously carried only a message string inherited from `AeatError`. The gap tests asserted `match=r"coverage=0"` and `"missing=" in str(exc.value)` — brittle to error-format changes.

Extended `DeclaracionParseError.__init__` to accept and store four typed attributes:
- `missing: tuple[str, ...]` — casilla IDs that produced no hit
- `malformed: tuple[str, ...]` — casilla IDs with unparseable values
- `ambiguous: tuple[str, ...]` — casilla IDs with multiple hits
- `coverage: Decimal | None` — extraction fraction; `None` for non-extraction errors

Updated `_extract_profile_values()` in `_parser.py` to pass these as keyword args when raising. The human-readable message string is unchanged so existing `match=` callers in other tests continue to work.

Rewrote both gap tests:
- `test_parser_modelo_130_corpus_numeric_casilla_profile_gap` (×15 parametrised corpus PDFs): asserts `err.coverage == 0` and `err.missing == ("01","02",...,"19")`.
- `test_parser_modelo_131_numeric_casilla_profile_gap`: asserts `err.coverage == 0` and `err.missing == ("01","02",...,"15")`.

Note: no M111 gap test exists — the audit's reference to "M111" gap tests was a misstatement; M111 has corpus round-trip tests, not a gap test. Only M130 and M131 carry gap tests.

## Verification

`pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py -k gap -v` → 17 passed.
