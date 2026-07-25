---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S190'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run suggestion and next-action conformance against the live tree

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`

## Description

Run suggestion and next-action conformance against the live CLI tree, attribute the residual
failure, then re-run at a later HEAD before reporting it as standing.

## Outcome

FAILED when measured, FIXED by the time of reporting. Both readings are recorded because the
first is what the audit found and the second is what the tree now holds.

First run. Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
Collected 8, 7 passed, 1 failed, exit line `1 failed, 7 passed in 11.10s`, exit code 1, at HEAD
`1844ef2ea0`. Reproduced identically on an immediate second run.

The defect: the refusal built by the ledger evidence-reference module told the operator to add the
document with the ledger evidence add verb carrying a file option. That verb takes a REQUIRED
POSITIONAL source path and exposes no such option; its options are supplier, invoice number,
invoice date, taxable base, iva rate, iva amount and notes. Confirmed at the time by invoking the
verb help against the live CLI. An operator following the suggestion verbatim got a usage error.

Re-run before reporting. Same command at HEAD `30176c2a2c`: collected 8, `8 passed in 11.51s`,
exit code 0. The suggestion string now names the positional form with no option. The correcting
commit is a gate fix that stopped citing a flag that does not exist.

## Notes

This is the reason the re-run discipline exists. The finding was real, reproducible and correctly
diagnosed, and it was closed by a peer between the measurement and the report. Reporting the first
reading alone would have sent the coordinator to fix something already fixed.

The two readings also settle the standard question the defect raised. The CLI verb standard mandates
a file option as the single-local-file input, and this command uses a positional. The fix chose to
make the suggestion match the command rather than the command match the standard. That choice is
recorded, not endorsed; whether this verb should grow the standard option is a separate decision for
its owner.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
