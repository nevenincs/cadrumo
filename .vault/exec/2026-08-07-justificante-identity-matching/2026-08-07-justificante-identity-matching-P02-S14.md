---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:aa8793b45c3d08d7c9c62c4793d4d1932a053db0823fe01d18e8f872ec1c8ec7'
step_id: 'S14'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---
# Narrow the application-layer relay test's name and docstring to what its assertions actually prove. It constructs the advisories onto the run model and reads them back off the same object, so it is a pydantic storage roundtrip that cannot fail when the CLI forwarding is deleted, while its name and docstring both claim to cover the relay. The fold itself is now covered at the transport boundary, so this is a truthfulness repair rather than a coverage gap. Gate: the renamed test still derives its expected set from the enum, and a reader can tell from the name alone that it proves the taxonomy has members and the model stores one advisory per member, not that anything reaches an operator

## Scope

- `src/cadrumo/application/live/tests/test_filed_history_onboarding.py`

## Description

- Renamed the module's advisory test to name the model-level property it asserts: the reason taxonomy has members and a run holds one advisory per member without merging them.
- Rewrote its docstring to state outright that it proves nothing about anything reaching an operator, that the advisories are written onto the model and read back off the same object, and that the forwarding is driven at the transport boundary instead.
- Renamed the local variable and the count comment from relay vocabulary to carrying vocabulary, and narrowed the taxonomy-size assertion message, which also claimed to be a relay test.
- Absorbed two sibling tests in the same module carrying the same overstatement in a lesser form: one comparing the run advisory builder's code against an evidence advisory, one asserting the empty default. Both were named for relaying and neither exercises a transport.

## Outcome

The module no longer claims transport coverage anywhere. A reader choosing where to add a forwarding regression is now pointed at the boundary rather than at a model roundtrip that would accept the change silently.

Deriving the expected set from the enum is unchanged, which was the row's explicit gate: the set still comes from iterating the reason type, so a newly added reason still widens the assertion automatically.

No coverage was removed and the boundary test was not weakened. The count of tests in the module is unchanged; only names, docstrings, one assertion message and one variable name differ.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/application/live/tests/test_filed_history_onboarding.py src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py
    26 passed in 4.24s

Both modules were confirmed selected rather than marker-deselected: both declare the unit marker, and a collect-only run of the boundary module reported "4 tests collected", accounting for 4 of the 26.

The central claim the new docstring makes -- that the test cannot fail when the forwarding is deleted -- is proven statically rather than by mutation, which is the stronger form here: a search of the module for any reference to the entrypoint or CLI layers returns nothing, exit status 1 for no matches. A module that imports no transport symbol cannot exercise the transport under any mutation of it, so no mutation window was opened. The boundary module reaches the forwarding function by direct import from the CLI module, which is the coverage the row relies on.

Type and lint gates on the module: ty check reported "All checks passed!", ruff format reported it unchanged, ruff check clean.

## Notes

The row scoped one test. Three carried the defect, all in the same module and all in the same direction, so the other two were absorbed rather than left as a known-false pair of names beside a corrected one. Nothing about their assertions changed.

Git reported a CRLF-to-LF normalisation warning on the module; the file was already tracked with that property and the warning is unrelated to the edit.
