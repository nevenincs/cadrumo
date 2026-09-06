---
tags:
  - '#audit'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:5c048d214927bfe43fd6b497a1c4b46ba6cac8f42a66edf20029b5cd471d703b'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# `cli-distribution-consolidation` audit: `import time collectability`

## Scope

A cross-cutting finding surfaced by this campaign rather than owned by it. The
packaging evidence lanes failed on a defect none of the owning suites could
see, and tracing it showed that one whole-tree gate is the only thing in this
repository able to see that class at all. Recorded here because a campaign's
audit is a durable home and two agent transcripts are not.

## Findings

### import-time-collectability | high | One gate holds a whole failure class, and its name understates it

`test_every_test_module_in_the_tree_is_collectable` reads as hygiene. It is the
only gate that can observe a module which does real work when imported, because
a module that dies at import cannot report which of its own assertions failed.
Its owning suite sees nothing: there are no results to read.

Three unrelated modules were uncollectable at once when this was found, and the
per-push lane had not been green for three days. They looked like one incident
and were not. A quality sweep executed five repository-rewrite passes from a
module-level dictionary; a registry proof constructed a validated provenance
constant whose value had gone stale against a tightened model; a documentation
test imported a symbol a rename had removed. Different causes, different owners,
one symptom, and one gate catching all of them.

Each was invisible where it was written. The sweep's own test asserted that its
apply flag was false, which stayed true while all five passes ran, so it passed
while the sweep was armed. The other two cannot report anything at all, because
the failure precedes their first assertion.

If that gate is ever marked flaky for being slow, or narrowed to a subtree,
three failure modes go dark together and the next occurrence surfaces wherever
the tree happens to be walked next -- which in this campaign was a packaging
lane on a different operating system, hours of work away from the cause.

### import-time-collectability | medium | The obvious preventive gate would be wrong

Banning work at module import is the wrong rule. A module-level constant built
through a validating model is good practice, and one of the three failures was
exactly that: its value had gone stale, not its placement. A gate forbidding
module-level construction would fire on hundreds of legitimate constants and be
switched off within a week, which leaves the repository worse than before.

The defensible line is narrower: a module-level call that touches the
filesystem or spawns a process. That is precisely what the sweep did and what
an ordinary constant does not do. Credit for the scoping belongs to the session
that owns the quality tooling; it is recorded here so the reasoning is not lost
with the transcript.

## Recommendations

Treat the collectability gate as load-bearing rather than hygienic, and say so
where its cost is next questioned. Its runtime is the price of the only view
this repository has into that class.

If the narrow gate is built, it belongs beside the existing rule that polices
what a package initialiser may import, not in a release campaign. The
scoping above is the design; the placement is the quality owner's call.
