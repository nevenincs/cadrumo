---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:993164c1c7559347989c9c5ab49a47e2a1080b9208181ba46d81afb1e094e89d'
step_id: 'S87'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Run the ledger's OWNING gates instead of the hand-rolled validation script this campaign had been substituting for them, and repair what they found: thirteen clusters authored here were missing the required area key, three clusters whose work was finished were never marked resolved, five had their symbols emptied although a cluster must name one, and two were step notes rather than symbol adjudications. Correct the collaboration-audit prose, whose claim that six emitters are unreached went stale when five were wired, and narrow the citation gate that had become unsatisfiable for a resolved entry.

## Scope

- `dev/audit/reachability_classification.toml`
- `dev/audit/tests/test_ledger_citations_resolve.py`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/audit/tests/test_ledger_citations_resolve.py`
- `verify:` `pytest dev/audit/tests/test_reachability_classification.py` 9 passed
  once the schema was repaired; `... test_ledger_citations_resolve.py
  ... test_classification_taxonomy_invariants.py ... test_ledger_measurements_are_dated.py`
  19 passed
- `verify:` module ratchet, secure-store gate, docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1038, exact 409
- `verify:` open symbol decisions 53 -> 52; clusters 122 -> 120

## Notes

The uncomfortable finding is about this campaign's own method. I have been
validating the ledger with a script written here -- closed class vocabulary,
evidence present, no symbol in two clusters, cited paths resolve -- and reporting
it as "ledger validated". The OWNING gates check different things, and against
them thirteen clusters authored here were malformed: every one was missing the
required `area` key, which the staleness check reads before it can compare a
cluster to the tree. That check has therefore been erroring rather than passing
for as long as those entries have existed.

Running the owning gate found three more things it had been unable to reach.
Three clusters whose work this campaign finished were never marked `resolved`
-- `discard_checkpoint`, `OptionalSourceUrl`, `ModeloDraftBuilderAdapter` -- so
the ledger went on asserting outstanding work on symbols the audit had stopped
reporting. Five clusters had their `symbols` list emptied to mean "done", which
is not how this file records that: `resolved = true` is, and a cluster must name
at least one symbol. Two of those were never symbol adjudications at all but
step notes, and their exec records carry them; they are deleted.

The collaboration-audit entry had gone stale in prose while its symbol list
stayed honest. It described six emitters as reached by nothing; five were wired
earlier in this campaign and removed from the list at the time, and only the
review-only-workspace emitter remains -- which is not an independent decision,
because nothing opens such a workspace, so there is no moment at which to emit.
The symbol-level gate could not catch that: it compares the list, and the list
was right. Prose is authorial.

The citation gate I added earlier had become unsatisfiable and is narrowed
rather than weakened. It required EVERY cited file to name a subject, which
forbids two honest shapes: a citation to a CONSUMER, where "nothing reaches
this" is actually proved, and any citation at all from an entry whose symbols
list is empty. It now requires every cited file to exist, and at least one to
name a subject -- so the defect it was written for, an entry citing only a
sibling, still fails. Two teeth cases added, including the bound that emptying
`symbols` does not licence a dead path.

`test_reachability_classification.py` still fails on fourteen orphaned test
modules that are neither entered nor under a classified module. A/B against
`git show HEAD:` of the ledger reproduces it exactly, so it is pre-existing and
not this step's; it is peer test work outrunning the ledger's orphaned-test
section.
