---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4a4457db6f4cbdc22bffd85dc79b97fcc3ceb9f1129da6b88004b67cca4bf421'
step_id: 'S114'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Pay the unpaid symbol-ratchet shrinkage and gate the orphan-test backlog against its classifications

## Scope

- `dev/quality/tests/test_orphan_test_records_agree.py`

## Changes

- `M` `dev/quality/unused_symbol_ratchet.toml`
- `A` `dev/quality/tests/test_orphan_test_records_agree.py`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_orphan_test_records_agree.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail`

## Notes

The symbol ratchet had been reported as red on two peer-introduced symbols for
several steps. That was wrong. It was red on those AND on unpaid shrinkage this
campaign owed: five module counts lowered by deletions made here, plus three
orphaned-test rows removed from the classification ledger four steps ago and
left standing in the ratchet. Both files describe the same population and only
one was paid.

With the shrinkage paid, the remaining red is exactly the two peer symbols:
`recapture_ledger_filing_evidence`, which re-bundles a sealed revision's
evidence so an operator who attaches a missing invoice is not at a dead end,
and `non_filing_axis_parameters`, one half of the two-way enumerability an
accepted event-date decision requires. Both are implemented, unwired, and
owned elsewhere. They are left red rather than absorbed: the ratchet forbids
raising a number, and its `[[intentional]]` mechanism is for symbols kept by
design, not for another contributor's unfinished feature. A red naming
someone else's open work is the gate doing its job.
