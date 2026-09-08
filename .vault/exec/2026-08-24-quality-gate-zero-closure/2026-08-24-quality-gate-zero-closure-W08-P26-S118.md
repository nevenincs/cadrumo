---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5f78f8a99e5627a44d921a6c44de84771c18eef86d51e766e6dceb004b49d529'
step_id: 'S118'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Close the absence-assertion class with canonical access or a site-naming declaration

## Scope

- `dev/quality/taxonomy_absence_conformance.py`
- `dev/quality/tests/test_taxonomy_absence_conformance.py`
- `dev/quality/tests/fixtures/taxonomy_absence_conformance.fixture`
- production test modules carrying checked `PINNED_TAXONOMY_LITERALS` declarations
- retirement of `src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py`

## Changes

- Added a real-tree AST sweep for taxonomy-related absence assertions.
- A site passes only when it routes through a verified canonical storage accessor, or its taxonomy token is present in `PINNED_TAXONOMY_LITERALS` and the adjacent rationale names both the containing function and token.
- Enforced both drift directions: a new raw site without a checked declaration is `undeclared-site`; a declared token without an executable source site is `stale-declaration`.
- Resolved assignments in source order, including conditional writes, nested scopes, annotated assignments, and assignment expressions.
- Verified canonical accessor origin rather than accepting an unrelated callable with the same name.
- Kept synthetic modules in the named, non-collected fixture corpus. The definition-line case is one physical line and distinguishes inclusive from exclusive function containment.
- Removed the superseded off-lane gate, `PENDING_UNDECLARED`, and the rejected parallel `PINNED_TAXONOMY_ABSENCE_SITES` mechanism. The only sanctioned declaration symbol is `PINNED_TAXONOMY_LITERALS`.

## Verification

- `uv run pytest -n 0 -q dev/quality/tests/test_taxonomy_absence_conformance.py` -> `69 passed in 19.04s`.
- The positive controls, greater-than-500-module anti-vacuity floor, real-tree sweep, canonical-accessor controls, and both declaration-drift directions all pass.
- Ruff lint, Ruff formatting, and `ty` pass for the detector and gate.
- The per-push marker expression collects all 69 taxonomy tests.
- A fresh external-`/tmp` mutmut 3.7.0 run selected 472 mutants, killed 462, left 10 survivors, and produced no other outcomes in approximately 58.2 seconds. The detector, gate, and fixture hashes stayed `2BE9BBA9...55CDEF`, `4CDF7BDC...6E93B9`, and `76F04811...CA4`.
- The 10 survivors were individually reviewed as inert: one impossible taxonomy placeholder; four declaration/rationale exclusion equivalents; two valid nested-span equivalents; one impossible equal AST position; one current-taxonomy subset equivalent; and one `UTF-8` codec alias. No mutation score was calculated or used.
