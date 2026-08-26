---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ee1bdd17e77a75310e2d4d3becdcf387472a47cfc642faacd77b5e6bb15cfa49'
step_id: 'S65'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Audit every closed Step against its execution record and repair the one closed without one, per the no-step-complete-without-a-record rule

## Scope

- `.vault/exec/2026-08-26-cli-root-verb-homes/`

## Changes

- `A` `.vault/exec/2026-08-26-cli-root-verb-homes/2026-08-26-cli-root-verb-homes-W05-P14-S39.md`
- `M` `.vault/exec/2026-08-26-cli-root-verb-homes/2026-08-26-cli-root-verb-homes-W05-P14-S35.md`
- `verify:` `python -c "...closed rows vs record files..."` -> `61 closed, 0 without a record`
- `verify:` `vaultspec-core vault check all` -> `no finding naming this feature`

## Notes

`aeat-agent-orchestration` states that no plan step may be marked complete
without a matching exec record, because otherwise delivered-as-specified,
delivered-narrower and recorded-but-not-implemented wear the same checkbox. That
invariant had never been checked on this campaign. It was violated once.

`W05.P14.S39` was closed with no record. The cause is traceable: seven rows
(S36-S42) had been lost from the plan document while their records survived on
disk, and the repair reconstructed the rows from those records' own headings.
S39 was the one row with no record to reconstruct from, so its text came from
the close audit's prose instead -- and nothing then noticed that the record it
could not be reconstructed from still did not exist.

The work was verified present before the record was written rather than inferred
from the checkbox: `test_transport_verb_grammar.py` ships and its four tests
pass.

The audit also ran the inverse direction, which is not what the rule guards but
is the way a record can mislead: two OPEN rows carry records. S34's already ends
by stating the benchmark census is not refreshed and why. S35's did not say it
was incomplete at all, while its machine-filled heading promises "Run the full
suite sequentially" -- so a reader meeting the record first would have taken the
Step for done. It now states that the row is open, that the heading promises
more than the record delivers, and what the standing goal still asks for that
the bounded slices exclude.
