---
tags:
  - '#adr'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:fe160f9ec4948400020516fd319309887ffa4aa4996b87a0eba5a141f0a916ee'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - '[[2026-08-31-tui-interface-command-path-population-measurements-reference]]'
---

# `tui-interface` adr: `command path production authority` | (**status:** `proposed`)

## Problem Statement

A notice can carry an action, and that action can carry the command an operator
would run. One entrypoint fills that command in and the other does not, so the
SAME notice from the SAME producer is actionable on one surface and a dead end
on the other: the operator is told there is no confirmed AEAT filing and
offered nothing to do about it. Two tests observe this directly.

The design that produced it is coherent, which is why nothing caught it.
Enrichment happens at the entrypoint because the mount paths are an entrypoint
fact, and the application layer must not import entrypoints. A second
entrypoint was added and the enrichment step was not, and both surfaces stayed
internally consistent while disagreeing with each other.

## Considerations

**The question is not where the mapping LIVES.** It already lives in the
application layer: `LiveLeafInventoryRow.canonical_cli_path` is an
application-layer field, and the CLI's own population site reads the path OUT
of that model and copies it onto the action. So the hexagonal direction is
already correct and deliberate -- application owns the model, entrypoint
populates it. What must be decided is which layer is responsible for PRODUCING
that population for EVERY entrypoint, rather than once per entrypoint that
remembers to.

**The layering objection is already not absolute in this codebase.** The
argument against an application-layer producer is that only an entrypoint can
know the mount paths. But `application/operator_surface/crud_registry.py`
declares literal command paths -- `"aeat app ledger evidence"`,
`"aeat app ledger invoice"` and four more -- on an application-layer contract
type. Six noun groups already assert CLI spellings from inside the application
layer. That does not settle the question, but it removes the claim that the
boundary forbids it outright.

**The Typer edge is a package namespace, not an import.** Two static analyses
disagreed about whether the authority depends on Typer (ten edges across 590
modules; zero across 493), so both were discarded and the module was imported
with `typer` and `click` blocked at the meta-path. It fails, and the traceback
names `entrypoints/cli/__init__.py` executing `import typer`. The authority and
its dependency closure are Typer-free; what is not free is importing anything
from that package at all, because the package initialiser runs. This is
invisible to any question of the form "does this module import Typer".

## Considered options

**A. The TUI imports the CLI's public authority.** Rejected. It inverts the
dependency direction between two sibling entrypoints and takes the Typer
dependency through the package namespace regardless of what the authority
itself imports.

**B. Relocate the authority into the application layer.** Measured: the
authority reads a graph of about 455 lines, and 75 files import that graph
against only 5 importing the authority. The consumer count is the price, and
it falls on the graph rather than on the thing being moved.

**C. Make the CLI package initialiser inert.** About 366 lines, roughly 55
re-exported names, 51 importing files. This is independently required by the
architecture rule on inert package initialisers and should happen on its own
merits, but it does not fix the notice by itself -- it removes one obstacle to
A, which is rejected for a second reason anyway.

**D. Reuse the existing operator-surface reconciliation.** Eliminated on
inspection: the reconciliation is Click-context aware BY DESIGN, keeping the
frozen inventory in Typer's context for the invocation so it has no
process-global lifetime, and no serialised artefact of it exists. Obtaining one
still means importing the CLI package. Same wall, different road.

**E. Generate the leaf inventory as a committed artefact from the live command
tree.** Not previously considered, and it follows an established pattern in
this repository rather than inventing one: `dev/docs/cli_reference.py` already
derives a reference from the live tree, and `generate_cli_reference_in_subprocess`
is specifically the technique for taking the Typer dependency in a child
process so the caller never imports it. Under E the application layer reads
DATA -- it neither imports an entrypoint nor hardcodes a path -- and a drift
gate compares the artefact against a fresh generation, exactly as the existing
generated references are gated.

## Constraints

Whatever lands must serve every entrypoint by construction, not by each one
remembering a step. The defect is a missed step, so a remedy that adds a step
the TUI must also remember reproduces it the next time a surface is added.

Option E's cost is a generated artefact, and this campaign already knows what
that costs: a generated file must be regenerated deliberately, it goes stale
silently between regenerations, and regenerating while the tree is being edited
bakes in half-landed work. Its gate must compare against a fresh generation
rather than against a frozen expectation.

## Implementation

E is proposed, with C landing independently on its own architectural merit. B
remains the fallback if a generated artefact is judged too much machinery for
one field, and its price is the 75-file graph move rather than the 5-file
authority move -- a distinction worth restating whenever the figure is quoted.

## Rationale

E is the only option that changes the SHAPE of the failure rather than paying
it down once. A, B and C all leave a per-entrypoint population step in place;
they vary in how expensive that step is to reach, not in whether a future
entrypoint can forget it. Under E there is nothing to forget, because the
mapping arrives as data the application layer already knows how to read.

## Consequences

Until this lands, `W01.P01.S118` cannot render a runnable command: it needs the
option-versus-positional distinction that the same authority carries. That row
inherits this decision and must not be picked up as independent work.

The defect is currently latent rather than live, which changes its priority
without removing it: measured on the reachable population, no producer routed
through the notice presentation gate carries argument bindings today, so
nothing is losing a call to action right now. The first binding-carrying notice
routed to a TUI surface will lose one silently, by dropping guidance rather
than erroring.

This ADR is `proposed`. The row it comes from states that the landing decision
is the operator's, because the chosen option moves a production surface and
cannot be attempted piecemeal.
