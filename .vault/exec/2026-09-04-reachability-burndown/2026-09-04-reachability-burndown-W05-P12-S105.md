---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e96595ba79c8f0e2191e2e7cd1d1eb61b3cde8357c63b6fa2adc245c8479cf4f'
step_id: 'S105'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Narrow the delegator sweep to the body shape the three deletions actually shared, returning only part of what a sibling returned, and correct the entry a previous pass got wrong: nineteen such delegators exist and sixteen are reached and legitimate, so the shape alone is not a defect and only an unreached one is. Delete the place-of-supply nature narrowing, whose docstring Raises clause documents what its callee raises rather than behaviour it adds, and record the two remaining unreached narrowings for a later step.

## Scope

- `src/cadrumo/domain/iva/place_of_supply.py`
- `src/cadrumo/domain/iva/tests/test_place_of_supply_grounding.py`
- `src/cadrumo/domain/iva/tests/test_classification_carries_place_of_supply.py`
- `dev/quality/unused_symbol_ratchet.toml`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/iva/place_of_supply.py`
- `M` two IVA test modules repointed at `place_of_supply_rule`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1029 -> 1028,
  exact 399 -> 398; the wrapper is no longer reported
- `verify:` `pytest` on both repointed modules 20 passed
- `verify:` symbol-ratchet entry removed as spent in this step; no shrink or
  spent lines remain
- `verify:` the four ledger gates 27 passed; module ratchet, secure-store gate
  and docstring ratchet exit 0
- `verify:` `ruff check` and `ty check` clean

## Notes

The sweep is the previous one sharpened to the body shape the three deletions
actually shared: `return sibling(...).attr` or `return bool(sibling(...))`.
Nineteen exist in the shipped tree and SIXTEEN are reached and entirely
legitimate -- `default_storage_root`, `get_active_master_key`,
`verify_modelo_revision` among them. A narrowing accessor is a normal thing to
write when something uses it, so the shape alone is not a defect and the
intersection with unreached is what makes it one. Three qualify.

One of those three is an entry a previous pass of mine got wrong, and how it was
wrong is the durable part. `required_supply_nature_for_rule` carries a `Raises`
clause distinguishing a rule that is not grounded from one grounded and silent,
and I read that as behaviour it adds. The clause documents what the CALLEE
raises. Its body is one line: `place_of_supply_rule(rule_id, on=on).supply_nature`.

Reading the body settled in a line what the docstring had argued the other way,
which is the same trap recorded earlier in this campaign when a module docstring
argued for a duplicate guard the action already performed. A docstring is
evidence about intent, never about behaviour.

The rule resolver carries six production references and the wrapper's four
consumers were all tests, which now read the field at the call site. The two
remaining unreached narrowings, `is_active_censo_modelo` and
`serialize_carried_objects`, are recorded for a later step rather than swept up
here: each has three to five test consumers to repoint, and one already belongs
to a censo cluster whose other members need their own re-test.
