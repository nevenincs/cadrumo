---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:190e4f03b372d1b5cbe1841c7aafda4c797651cabc649c64c7751d8916f0d216'
step_id: 'S22'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S22

## Outcome

**Not landed, and deliberately so.** The Step's qualifier — "each completing an already-argued intent rather than making a new decision" — is the gate, and neither available fix passes it tonight.

## What is actually red

**One ruff violation, tree-wide.** `I001` (unsorted import block) in `src/cadrumo/core/tests/test_atomic_write.py`. That file carries **uncommitted peer WIP** (` M` against HEAD), so the violation lives inside someone else's in-flight edit. Fixing it would rewrite lines a peer is holding, which `uncommitted-wip-is-not-orphaned` forbids regardless of how mechanical the change looks.

**Three size-budget gates.** Eleven modules exceed their declared band. The regeneration route the Step's "ratchet" framing implies is explicitly refused by the gate's own message:

> a plain `python -m dev.audit.size_budget --write-baseline` will NOT lift a ceiling you broke through

So the remedy is extraction, which is a design decision per module, not a mechanical fix. Regenerating anyway would bake tonight's tree-wide churn into the ratchet — loosening a budget to match the code is how a size gate stops measuring anything.

## My own contribution, stated rather than netted out

`_ledger_bindings.py` is 1843 lines against a 1335 limit. The `W02.P03.S07` reachability probe added roughly 58 of those. The breach predates that by about 450 lines, but the addition is real and is recorded here rather than excluded on the grounds that the file was already over.

I did not trim it back. The bulk of those lines are the docstrings `W05.P07.S08` requires — the explicit statement of what the probe cannot catch, including the tautology on the casilla-keyed family. Shortening them to buy budget would undo the Step that asked for them.

## Why extraction was not attempted on that one module

Extracting the probe machinery into a sibling module is exactly what the gate asks for, and it is a cohesive concern. It was not done because the file is under active peer modification: `c155b2aa28` and `75968fd8fa` both edited the probe itself within the hour, adding the `applied_rate` axis to the selector and the probe shape together. A cross-module extraction of code a peer is editing right now is the collision the worktree disciplines exist to prevent, and it would land on top of their work rather than beside it.

## Disposition

Left unchecked. Two concrete preconditions, either of which makes this executable:

- the peer WIP on `test_atomic_write.py` lands, freeing the one-line import fix;
- `_ledger_bindings.py` settles, at which point the probe extraction is a clean, cohesive move that reduces the largest single breach the campaign contributed to.
