---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:153c936daecfa4b62c69d0014c3933d7034cba8052ec7b75691e393efccd3a4b'
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
- Kept source specimens in named non-collected fixtures; the gates exercise real parsing and filesystem behavior without mocks or monkeypatches.
- Tightened subsuming-disjunction matching to stable name haystacks and structural AST equality.
- Bound self-echo findings to the nearest preceding same-scope invocation assignment and treated later writes, destructuring, loop/context/exception targets, definitions, and imports as binding barriers.
- Added negative controls for effectful and attribute haystacks, nested scopes, same-line ordering, overwritten results, and supported binding-barrier forms.

## Current subsumption verification

- Exact identities: detector `5D74756B3E02C282C0E4E71787F0834202B3E120BE418B7D386194718FB605E8`, gate `CA675F02EA16B9A9917BFD3FD3A79536102EEF179C77E008C15510CC90A11B31`, and fixture `EECF07EF6C2F204655E89AB0329C6363BCCD5E1B0F73090CBF0D26E7A6317ECF`.
- The focused baseline passed all 14 tests in 5.92 seconds.
- Pinned mutmut 3.7.0 selected 75 mutants and killed 69 in 212.92 seconds, with no error, suspicious, timeout, no-test, skipped, or typecheck outcomes.
- Six survivors were inspected individually and are semantically inert: the equivalent `UTF-8` codec alias; `ast.dump(include_attributes=False)` changed to `None`; omission of that default-false keyword; selection of the second structurally equal haystack; and two changes confined to `ast.parse` exception filename metadata.
- The previously actionable path-attribution and ambient-decoding mutations are killed by the current same-process filesystem control.
- No mutation score was calculated or used.

## Other detector mutation proof

- Tautological-assertion detector: 77 selected, 76 killed, and one individually disposed equivalent codec-alias survivor.
- Self-echo evidence is recorded only for an exact current detector/gate identity; superseded runs are not transferred across source changes.

## Review

- Formal review is recorded in `[[2026-09-07-quality-gate-zero-closure-s112-detector-gate-review-audit]]`.
