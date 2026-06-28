---
tags:
  - '#research'
  - '#metastate-zero-tolerance'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
---

# `metastate-zero-tolerance` research: where migration-progress lists accreted in production code

## Findings

### Three accretion shapes were inventoried

Coverage gates carried "modules without paired tests yet" allowlists.
The canonical example is the `COVERAGE_GAPS` 66-entry frozenset in
the inventory module that the coverage-canonicalisation audit
retired in one commit. Every entry was a process note ("not yet
enrolled"); none carried structural rationale.

Protocol-registration sites carried inline lists of "concrete classes
not yet behind a Protocol". The hexagonal-port-necessity audit found
four bucket-A ports where the Protocol was authored but no
application-layer consumer type-hinted it. The drift surface was
itself a metastate: a list of "ports that should be wired soon".

Docstrings and comments named the wave, phase, or step that
introduced the current shape ("added in W12.P26.S314", "pending W13
enrollment"). These references rot the instant the campaign closes;
they outlive their relevance by orders of magnitude.

### Three acceptable outcomes when a migration introduces a list

The list can be eradicated in the landing commit by driving every
entry to its destination state. This is what the
coverage-canonicalisation eradication wave did with the 62 bucket-C
entries: one commit added the AST import-graph helper, deleted the
entries, and the constraint they encoded vanished into a structural
rule.

The list can be retained with per-entry rationale that justifies
each entry on durable structural grounds. The retained 9-entry
`_EXEMPTIONS` set in `test_every_module_has_test_coverage.py` is the
canonical worked example: each entry carries an inline comment
naming the durable reason (browser-only dependency, `_lazy()`
Typer subcommand, `python -m` entry point, CLI integration shim).

The list can be deleted because the constraint it encoded was a
process artefact that does not need to be enforced at all. This
applies to "modules touched in this campaign" lists, "callers swept
in this pass" lists, and similar artefacts whose only purpose was
to coordinate the campaign that introduced them.

### Why automatic detection is wrong

The shape "is this list metastate or a real rule" requires human
judgement on the per-entry rationale. A list of nine entries each
named with a one-line structural rationale is durable; a list of
nine entries each named with "TODO: enroll" is metastate; a
detector cannot distinguish them without reading the comments.
Enforcement is therefore a review gate, not a CI check.

## Decision

Carried in the related ADR
`2026-06-01-metastate-zero-tolerance-adr` and the project memory
`metastate_zero_tolerance.md` (which the ADR ratifies as durable
authority).
