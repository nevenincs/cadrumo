---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b641a8e211eeffb480806d10bc1d5f72e782e40fa7b22a1c75a918c4ff3e6165'
step_id: 'S58'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# author the identifier-enrollment ratchet test asserting every production pydantic field whose name matches the namespace vocabulary carries a `core.identity` namespace alias rather than bare `str`, with `Declaracion.estado`, `Deuda.situacion`, and the three free-text sub-populations from `W07.P11.S48` as named, documented exclusions

## Scope

- `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`

## Outcome

The ratchet reads the current working tree under `src/cadrumo`, not a pinned commit. It excludes `tests` and `generated` directories and explicitly skips Pydantic `PrivateAttr` declarations, which are implementation state rather than model fields.

The unenrolled baseline and every baseline-specific test were deleted. The only exceptions are 30 live, bare-by-design fields in the single `_ADJUDICATED` ledger. Each is keyed by `(path, model, field)`, has a group and a reason, and is anchored by `test_no_stale_adjudication`; stale, renamed, removed, or typed entries now fail. Every other identifier-named bare `str` field fails the ratchet immediately.

The gate retains the derived alias vocabulary, the shared `tax_id` stem, free-text population anchors, and structural `short_` companion control. It adds a direct scanner test proving that a Pydantic `PrivateAttr` is excluded while a real bare `transaction_id` field remains detected.

## Verification

- `uv run --no-sync pytest src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py -q` â€” 10 passed.
- `uv run --no-sync ruff check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.
- `uv run --no-sync ruff format --check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.
- `uv run --no-sync ty check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.
- `git diff --check -- src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.

## Notes

This Step owns only the ratchet and its explicit adjudications. It makes no production retype, does not encode a fixed-count baseline, and does not claim coverage of parameters, returns, dataclasses, tests, or generated source.
