---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:90c04bcf3a1d04c4f46d62b3c7a941917859891b72fcdb14c9fdfa8795ab7dc0'
step_id: 'S203'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the authoritative typed duplication runner and require zero clones for green, clone findings for amber, and unavailable, failed, timed-out, non-zero, or unparseable execution for explicit amber-unavailable without false green

## Scope

- `dev/audit/duplication.py`
- `dev/audit/report.py`
- `justfile`

## Description

Run the authoritative typed duplication runner and prove it discriminates between a genuine
zero, clone findings, and an unavailable execution.

## Outcome

SATISFIED, and the instrument is PROVEN to discriminate.

Real scan. Command: `uv run --no-sync python -m dev.audit.duplication`. Output line `duplication:
12 clones, 0.07% duplicated lines.`, exit code 0. Corpus non-empty, proven by twelve enumerated
clone pairs. This is the clones outcome, rendered amber by design, not a green claim.

The twelve pairs, by owning module: two registry oracle modules sharing a preamble; a TUI form
screen against a TUI manager screen, and the form screen against itself; two modelo work payload
modules; a ledger LLM CLI module against itself; an attachments service against itself; a calendar
models module against itself; a calculation source staging module against itself; a ledger models
module against itself; a renta gasto ledger against a renta income ledger; an impatriado income
ledger against that same renta income ledger; and a diagnostics run-health module against itself.

Discrimination probes, run in-process against the real runner with no patching, using its injected
executable-resolver seam. Against an EMPTY source root the runner returned outcome `unavailable`
with `files_analyzed = 0` and the reason that the scan produced no parseable summary, which is also
how a run matching zero files renders. Against a resolver returning no executable it returned
outcome `unavailable` with the reason that the tool was not found on PATH. Neither degraded case
rendered as a zero-clone green.

There is exactly one clone-detection command in the tree. Exact search for the tool name returns
one command builder and one version constant, both in the runner module. The two consumers, the
health report and the justfile recipe, both route through that module: the report imports the
scan function and the outcome enum, and the recipe both executes the module and reads its version
constant rather than restating it.

## Notes

The runner's own documentation states the limitation that matters for reading this result:
it matches token sequences, so a concept implemented twice in different syntax is invisible to it.
A low percentage means little copy-paste survives; it has never meant little duplication survives.
The semantic half of that question is covered under S205 and S206, and the semantic instrument was
degraded.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

SATISFIED (AMBER). One additional clone pair appeared since the original reading.
Command: `uv run --no-sync python -m dev.audit.duplication`.
Output line `duplication: 13 clones, 0.08% duplicated lines.`, exit code 0, at HEAD `bc80aa2808`.

The thirteen pairs, by owning module: two censal-datos modules sharing a preamble block
(new pair since original reading, from censal-datos campaign); two registry oracle modules
sharing a preamble; a TUI form screen against a TUI manager screen, and the form screen
against itself; two modelo work payload modules; a ledger LLM CLI module against itself;
an attachments service against itself; a calendar models module against itself; a calculation
source staging module against itself; a ledger models module against itself; a renta gasto
ledger against a renta income ledger; an impatriado income ledger against that renta income
ledger; and a diagnostics run-health module against itself.

None of the thirteen pairs is in this feature's modules. The discrimination probes from the
original reading remain valid: the runner has not changed and the test seams it exposes are
unchanged.
