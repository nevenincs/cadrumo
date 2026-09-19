---
tags:
  - '#reference'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1eba4dd21dfe1c8ccd9eb1284340cc492c43ecfaf06190678242e2fa7f20f11e'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# `tui-interface` reference: `command path population measurements`

What was measured on 2026-08-31 about where a notice's runnable command comes
from, recorded separately from the decision it grounds because two of the three
findings correct figures that were previously quoted.

## Summary

### The mapping already lives in the application layer

`LiveLeafInventoryRow.canonical_cli_path` is an application-layer field, and
the CLI's own population site reads the path OUT of that model and copies it
onto the action. So the hexagonal direction is already correct: application
owns the model, entrypoint populates it. What is entrypoint-bound is the
POPULATION of the inventory, not the mapping.

### It is populated at two sites, not one

The figure previously quoted was one. There are two on the notice path: one
reads the path from the live-leaf inventory, the other copies it from the
command-spec schema. Only one of them is the enrichment the second entrypoint
fails to perform, but a remedy that assumes a single site would miss the other.

### The application layer already declares literal command paths

Six noun groups in the operator-surface CRUD registry carry literal `aeat ...`
strings on an application-layer contract type. This does not settle where the
authority belongs, but it refutes the claim that the boundary forbids an
application-layer producer outright -- the codebase already accepts that shape
for a different family.

### The Typer edge is a package namespace, not a module import

Two static analyses disagreed (ten edges across 590 modules; zero across 493),
so both were discarded and the module was imported with the offending packages
blocked at the meta-path. It fails, and the traceback names the CLI package
initialiser executing its import. The authority's dependency closure is clean;
what is not clean is importing anything from that package at all. No question
of the form "does this module import Typer" can see that.

### A generated artefact is an available technique here

The repository already derives a CLI reference from the live command tree, and
does so in a SUBPROCESS specifically so the caller does not take the
dependency. That is the same wall the inventory hits, and it has an established
way through it.
