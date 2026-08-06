---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:7fe9c62df8b0c20f13318b39dc115db002edae968f98ab890c0da2d4f1c04200'
step_id: 'S08'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Write parser unit tests covering grammar acceptance, every refusal case, capture and expect binding, and seed inlining

## Scope

- `dev/docs/sequences/tests/test_parser.py`

## Description

- Add `tests/test_parser.py` proving the ADR D1 worked example parses into the expected typed frames with every capture, expect, placeholder, and argv preserved, and that JSON literals parse typed by kind (string, int, bool).
- Cover every refusal mode with its message: missing/blank verify, zero/multiple/non-terminal result, result without expect, unresolved placeholder, own-frame placeholder, nested fence, unrecognised line, sigil non-aeat command, capture before any frame, malformed and unquoted expect, duplicate capture, unknown sigil, and invalid placeholder shape.
- Prove independent faults accumulate together in one pass rather than aborting on the first.
- Add `tests/test_seeds.py` driving real seed files on disk: inlining order, seed-capture threading into a body placeholder, missing recipe, and seed-only enforcement for visible-command and result frames.

## Outcome

All 30 tests pass with no mocks, skips, or xfail. Ruff lint and format are clean and `ty` type-checks the package with no errors. Tests use real on-disk seed files under `tmp_path`; assertions derive from the ADR grammar, not from parser output.

## Notes

The dev/docs test convention requires exactly one `hex_*` marker; the tests carry `unit`, `hex_core`, and `docs`. No skipped or tautological assertions.

Review cycle: the initial parser commit was reviewed PASS-WITH-FINDINGS, closed by a follow-up commit that fixed the unbalanced-placeholder-brace silent miss, bounded the sequence id / seed name / verify length in the parser off the shared schema constraints (so an over-long value accumulates as a parse error rather than a raw pydantic ValidationError), required an integer literal for the exit_code expect, located the duplicate-capture diagnostic at the capture line, and derived the parser regexes from the schema patterns pinned by a parity test. The re-check confirmed all findings closed with the typed surface unchanged. Test count rose from 30 to 40.
