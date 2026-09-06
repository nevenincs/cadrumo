---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:aabc4dd3d8833d6ee7da280e794acf07c856ec403d0ef6f6127a5a50e4995f34'
step_id: 'S448'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Confirm a locale-key row table through its key column rather than any unpacked name. The row-table rule identifies which column holds keys and then confirms the table if ANY loop name reaches a translator sink, so a guard table whose English refusal reaches a raise was read as a locale-key table and its canonical command keys were demanded as translations. Bind each unpacked name to its column index and confirm only on a key column, keeping the whole-row binding and the genuine key-column-reaches-tr shape working.

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Locale parity missing keys: 5 -> 1. The remaining four were a second false
positive in the scanner, and a different one from S447's, which is why the
previous Step declined to extend that rule by assumption.

The row-table rule is careful about SHAPE and loose about CONFIRMATION. It finds
a table of equal-width string rows with at least one column where every row is a
dotted key -- deliberately allowing the sibling columns to be prose, because the
framework tables it was written for carry English source strings beside their
keys. It then confirms the table if ANY name unpacked from the loop reaches a
translator sink.

ledger/action_guards.py is that shape without being that thing. Its rows are
(attribute, canonical command key, English refusal), and the loop ends in
`raise ValueError(refusal)`. The prose column reaching a sink confirmed the
table, and the key column -- ledger.review, ledger.classify, ledger.link,
ledger.evidence.review.list -- was collected as translations to demand. Those
are canonical COMMAND keys the catalogue should never carry.

Confirmation now binds each unpacked name to its column index and accepts only a
key column. A whole-row binding still confirms as before, since it cannot say
which column reaches the sink and narrowing it would be a guess in the other
direction.

Teeth pin both directions in one test, because the risk here is over-correction
rather than under: the guard table's prose sink must NOT confirm, and a genuine
`for prefix, key, default in TABLE: tr(key)` must still collect its key.
Reverting to any-column confirmation fails it. Restored by copy; 18 passed.

## Notes

One missing key remains: tui.ledger.reconciliation.direction, from
ledger/controller.py. It is a THIRD construct again, so it gets its own look
rather than a third assumed extension.

454 extras are unchanged. Nothing in this Step touches them, and scaffold still
must not be used to prune them.

An observation, not a defect fixed here: the guard refusals are English literals
raised through ValueError rather than locale keys. They read as developer-facing
invariant messages -- an injected action failing to resolve is a composition
error, not operator input -- so leaving them unlocalized is defensible. Recording
it because the scanner's interest in that table is what surfaced them.
