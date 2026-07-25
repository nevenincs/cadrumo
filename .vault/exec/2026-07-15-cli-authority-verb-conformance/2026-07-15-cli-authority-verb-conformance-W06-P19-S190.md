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

Run suggestion and next-action conformance against the live CLI tree and attribute the
residual failure.

## Outcome

FAILED, genuine committed defect on an operator-facing surface.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
Collected 8, 7 passed, 1 failed, exit line `1 failed, 7 passed in 11.10s`, exit code 1, at HEAD
`1844ef2ea0`. Reproduced identically on a second run.

The refusal built by the ledger evidence-reference module at line 234 tells the operator to add
the document with the ledger evidence add verb carrying a file option. The live command takes a
REQUIRED POSITIONAL source path and exposes no such option at all; its options are supplier,
invoice number, invoice date, taxable base, iva rate, iva amount and notes. Confirmed by invoking
that verb's help against the live CLI.

The owning file is clean at HEAD, so this is committed state, not peer working-tree churn. It
landed with the commit that defined the evidence-reference id space once.

## Notes

An operator who follows this suggestion verbatim gets a usage error. This is the dead
instruction class the CLI verb standard's mandatory hand-sweep exists to prevent.

There is a second-order question for the owner, recorded but not decided here: the same standard
mandates a file option as the single-local-file input, while this command uses a positional. The
suggestion can be made correct either by growing the command the standard option or by rewriting
the suggestion to the positional form. Only the second is a conformance fix.

Remediation is not performed in this Phase; the Phase audits and attributes.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
