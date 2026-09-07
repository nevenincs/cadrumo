---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3939cd8b925460048d535061e7366542a6cbe670129b1d5260272a1f5b6ae989'
step_id: 'S106'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Repair the dangling docstring reference the previous deletion left, which the reference ratchet caught and which a transient-looking red had already hinted at, then take the deferred custody-carry narrowing: it dropped the coverage manifest and the refusal beside it, since the live payload builder returns the rows with their namespace-coverage fact and raises when a full profile carries unclassified namespaces, so a caller reaching for the shorter name got rows where the product refuses. Point its five test consumers at the payload builder rather than the private helper it narrowed.

## Scope

- `src/cadrumo/domain/iva/place_of_supply.py`
- `src/cadrumo/application/user_profile/custody_carry.py`
- `src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/iva/place_of_supply.py`
- `M` `src/cadrumo/application/user_profile/custody_carry.py`
- `M` `src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `docstring_reference_ratchet` red -> exit 0
- `verify:` `python -m dev.audit.unreachable_code` unused 1028 -> 1027,
  exact 398 -> 397
- `verify:` `pytest .../test_custody_roundtrip.py` 3 passed
- `verify:` symbol-ratchet entry removed as spent in this step; no shrink or
  spent lines remain
- `verify:` the four ledger gates 27 passed; module ratchet and secure-store
  gate exit 0; `ruff check` and `ty check` clean

## Notes

I broke the docstring-reference ratchet in the previous step and shipped it. The
deleted place-of-supply wrapper was named in its own module docstring, and the
sentence explaining refusal-rather-than-a-guess went on citing it. Worse than
the breakage is that I had seen a red from that gate one step earlier, re-ran
it, saw green, and moved on -- the two runs were not measuring the same thing
and I treated the disagreement as noise. A red that disappears on a re-run is a
question, not an answer. The sentence now describes the field on the rule rather
than the deleted accessor, and the ratchet is green.

The custody-carry narrowing is the fourth findings-discarding variant this
campaign has removed and the strongest of them. It dropped the coverage manifest
AND the refusal beside it: the live `build_secure_object_custody_payload` returns
the rows with their exact namespace-coverage fact and raises `ProfileExportError`
when a FULL profile carries unclassified namespaces. A caller reaching for the
shorter name got rows back where the product refuses.

Its target's VISIBILITY changed where the tests point. `_carry_material` is
private, so deleting the wrapper and sending tests there would have pushed them
onto a private name -- the opposite of the boundary rule. They point at the
public payload builder instead and discard the manifest explicitly at the call
site, which is the honest shape: the discarding is now visible in the test
rather than hidden in a function.
