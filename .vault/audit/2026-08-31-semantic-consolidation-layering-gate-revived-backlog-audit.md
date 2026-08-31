---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e27d46b65684e811353e4f5c20dee1d6ab21a9492571e95e19c4368735a2f46f'
related: []
---

# `semantic-consolidation` audit: `layering gate revived backlog`

## The gate is running again, and it has a backlog

`lint-imports` was reported dead earlier today by another session: it aborts on
the first syntax error it meets, prints a single narrow complaint, and evaluates
ZERO contracts. In that state it is indistinguishable from a passing gate.

The tree now parses on both roots, so the gate runs. It analyses 5,699 files and
35,024 dependencies, keeps most contracts, and reports:

- **`AEAT layered architecture` BROKEN** -- 82 unexempted edges
- **`Backend and sibling entrypoints must not depend on the dedicated TUI` BROKEN**

## The 82 are pre-existing, not campaign-created

The obvious suspicion is that this campaign caused them: retiring a facade
repoints consumers at defining modules, and an exemption naming the namespace
would stop matching once the import names a submodule instead. That would
convert allowed edges into violations without anyone writing a new import.

It was checked rather than assumed, by reading the same import line at `HEAD`
and in the working tree:

| module | at HEAD | now |
| --- | --- | --- |
| `application/ledger/llm_diagnostics.py` | `from ...adapters.outbound.llm._usage import UsageRecorder` | identical |
| `application/ledger/evidence_input.py` | 8 references | 8 |
| `application/ledger/aeat_record_projection.py` | 3 references | 3 |
| `application/ledger/counterparty_establishment.py` | 1 reference | 1 |

The first is exact: the violating import is byte-identical at `HEAD`. These
edges predate the campaign and were simply invisible while the gate aborted.

`.importlinter` already carries the shape that would exempt one --
`cadrumo.application.diagnostics_run_health -> cadrumo.adapters.outbound.llm._run_telemetry`
at line 516 -- so the neighbouring `llm_diagnostics -> ._usage` edge is
unexempted rather than unexemptable. Whether each of the 82 is a real violation
to fix or an exemption to add is per-edge work and is NOT this campaign's.

## The pattern, for the third time today

A detector that fails open reports nothing and reads as clean. This session has
now recorded three instances:

- `lint-imports` aborting on a syntax error, reporting one narrow complaint
  while evaluating no contracts
- a git-tracked filter for the production scan surface, which would have hidden
  56 uncommitted modules -- rejected under `P08.S173` before it was built
- a post-write damage scan that walked `src/` while the rewriter also wrote to
  `dev/`, reporting "0 files fail to parse" while another lane watched the error
  count climb into the thousands

The three differ in mechanism and are identical in effect: a true number about
the wrong population, reported in the words of a clean result.

## What is owed here

Nothing from this campaign, and that is the point of recording it. The 82 edges
are architecture debt that became visible when the tree was repaired, and they
belong to whoever owns the layering contract. Recorded so the next session to
run `lint-imports` reads a known backlog rather than a fresh regression, and
does not attribute it to the retirement work.

## The second broken contract is a design question, not a repair

`Backend and sibling entrypoints must not depend on the dedicated TUI` breaks on
two CLI modules:

- `entrypoints/cli/_modelo_work_review_cli.py`
- `entrypoints/cli/_modelo_work_select_cli.py`

Both are pre-existing: the TUI reference counts are identical at `HEAD` (3 and
9) and in the working tree.

The imports are not accidental. They are function-local and deferred --
`from ...entrypoints.tui.modelo.view.work_select import ModeloWorkSelectApp`
inside the branch guarded by `tui_was_requested` -- so the TUI is loaded only
when the operator asks for it and never at CLI startup. Someone wrote them that
way on purpose.

So the contract and the feature disagree, and the disagreement has two honest
resolutions:

1. The CLI is MEANT to launch a TUI view on request, and the contract needs an
   exemption naming these two deferred edges.
2. The dependency should invert: the CLI declares an outcome and a launcher
   resolves it, so the CLI names no TUI module. `entrypoints/tui/modelo/routes`
   already carries `WORKSPACE_SELECTION_OUTCOME` and `resolve_destination`,
   which suggests that inversion was at least considered.

Neither is a mechanical fix, and choosing between them belongs with whoever owns
the TUI boundary -- a lane that is actively working `entrypoints/tui` right now.
Recorded rather than resolved, and deliberately not folded into the
consolidation campaign: retiring facades and adjudicating an entrypoint
boundary are different questions that happen to be visible in the same gate
output.
