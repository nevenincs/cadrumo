---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e1a75f61d266f17d73e6d3054d23e973807f4f726efccf7215cf15e25403a55c'
step_id: 'S112'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Give every detector a gate carrying a positive control that fires on a representative defect and an anti-vacuity floor that fails when the swept population collapses, refusing any detector that ships without both, and kill each detector's own gate with mutmut (Luna max audit and mechanical)

## Scope

- `dev/quality/tautological_assertion_scan.py`
- `dev/quality/subsuming_disjunctions.py`
- `dev/quality/self_echoing_tokens.py`
- `dev/quality/tests/test_tautological_assertion_gate.py`
- `dev/quality/tests/test_subsuming_disjunctions.py`
- `dev/quality/tests/test_self_echoing_tokens.py`
- `dev/quality/tests/fixtures/`
- `pyproject.toml`

## Changes

- Added a real-tree sweep, a representative positive control, and a per-root anti-vacuity floor for each of the three detector gates.
- Kept the controls on real parsing, filesystem, locale, and binding behavior; the gate tests contain no mocks or monkeypatches.
- Tightened subsuming-disjunction matching to stable name haystacks and structural AST equality.
- Bound self-echo findings to the nearest preceding same-scope invocation assignment and treated later writes, destructuring, loop/context/exception targets, definitions, and imports as binding barriers.
- Added negative controls for effectful and attribute haystacks, nested scopes, same-line ordering, overwritten results, and every supported binding-barrier form.

## Verification

- `uv run pytest dev/quality/tests/test_tautological_assertion_gate.py dev/quality/tests/test_subsuming_disjunctions.py dev/quality/tests/test_self_echoing_tokens.py -q` -> `79 passed in 18.46s`.
- `uv run ruff check dev/quality/tautological_assertion_scan.py dev/quality/subsuming_disjunctions.py dev/quality/self_echoing_tokens.py dev/quality/tests/test_tautological_assertion_gate.py dev/quality/tests/test_subsuming_disjunctions.py dev/quality/tests/test_self_echoing_tokens.py` -> pass.
- `uv run ruff format --check ...` over the same six files -> `6 files already formatted`.
- `uv run ty check ...` over the same six files -> pass.
- `rg -n "monkeypatch|unittest\\.mock|\\bmock\\b"` over the three gate tests -> no matches.

## Mutation proof

- Ran bounded native mutmut from retained isolate `/home/hello/cadrumo-s112-native-0bfb79a380244bd4904b600a45a925ab`, with the parent environment and exact source/test/fixture bytes.
- Tautological-assertion detector: 76 of 77 mutants killed; the sole survivor changes codec spelling from `utf-8` to `UTF-8`, which is behaviorally equivalent.
- Subsuming-disjunction detector: 69 of 75 mutants killed; all six survivors are equivalent or verdict-inert (codec spelling, `SyntaxError.filename` metadata, omitted/default-false keyword forms, and selection between structurally equal haystacks).
- Self-echo detector: 139 of 143 mutants killed on the final exact snapshot. The four survivors are equivalent or verdict-inert: two affect only `ast.parse` filename metadata, one changes `continue` to `break` after descending token-length sorting once all remaining tokens are also short, and one changes `<` to `<=` where a single AST node cannot be both the assignment and the later assertion.
- All behavioral survivors were killed. In particular, the final real-syntax controls killed the prior starred-unpack, context-manager, exception-target, dotted-import, and aliased-import binding mutations.

## Review

- Formal review is recorded in `[[2026-09-07-quality-gate-zero-closure-s112-detector-gate-review-audit]]`.
