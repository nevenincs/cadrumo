---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S66'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# take the whole verification-predicate concern out of the registry schema module in one commit that also owns and removes its size-budget baseline entry, since the concern is larger than the pinned band allows and half-taking it would scatter one concept across two modules

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Move the predicate model, the closed operator vocabulary the registry-build
  validator reads, and the profile-flag field allowlist two of those operators
  consume, into the verification sibling the previous extraction created.
- Widen the sibling's module docstring to state that it now owns both layers of
  one verification strategy, and why the vocabulary travels with the model.
- Repoint the five sites that named the schema module directly: the surface
  validator, the predicate validator, the package facade and two intra-package
  test modules.
- Correct the two prose sites that gave the old module path as the canonical
  home of the operator set.
- Remove the schema module's size-budget baseline entry, which the extraction
  turns into dead weight.

## Outcome

One commit, `7007840311`, with an explicit nine-path pathspec. The registry
schema falls from 1386 to 1088 lines and leaves the pinned population entirely;
the sibling grows from 148 to 465 lines and needs no entry.

**The band was the whole obstacle, and owning the baseline removed it.** The
previous extraction measured the constraint exactly: the ratchet fails an entry
that grows past its limit, one whose limit drifts further above it than the slack
tolerance, AND one that falls to or below the 1250 default as dead weight, which
put the legal band at 1334 to 1483 and capped any extraction at 148 lines. The
predicate concern is 300 lines, so it could not land inside the band under any
seam. That analysis was re-confirmed empirically rather than inherited: restoring
the entry after the move reproduces "pinned at 1483 but measures 1088, within the
1250 default; the entry is dead weight". Removing the entry is therefore required
by the move, not a convenience alongside it, and no ceiling was lifted anywhere.

**All three symbols moved, because two would have scattered the concept.** The
predicate model documents each DSL operator's semantics in a 143-line class
docstring; the operator vocabulary is a 142-line annotated constant the
registry-build validator checks every expression against. They are one concept
documented twice, so taking one without the other was the bad extraction the
previous Step refused. The profile-flag field allowlist went with them for the
same reason: it is the argument vocabulary of two of those operators, read only
by the predicate validator, so leaving it behind would have stranded a third
piece of one concept in a module that no longer declares the concept.

**The sibling is the right home, stated rather than assumed.** It already owned
the expectation declaration and its snapshot fold. Expectations say which
casillas a filed return is compared against; predicates say which relations
between casillas must hold; a filing is granted only when both are satisfied. The
docstring now carries that framing so a reader arriving at either half
understands why the other is there.

**Behaviour was proven, not asserted.** All three symbols were dumped as abstract
syntax trees before the move and compared against the sibling afterwards: all
three identical, including docstrings, because the bodies moved verbatim. Every
string literal inside them was extracted and compared in sequence - 2, 17 and 4
respectively, identical - so the operator names the registry-build validator
matches on and the refusal messages tests and operators key on are unchanged.

**No field moved between models, so nothing reordered.** The hazard the earlier
extraction recorded - that a mixin reorders a pydantic model because inherited
fields are placed first, silently changing serialisation order - does not arise:
whole symbols moved, and the predicate model's four field declarations travelled
inside their own class body. That was checked rather than reasoned, by the AST
comparison, which is field-order-sensitive.

**Consumer sweep, and one deliberate non-change.** Five sites named the schema
module directly and now name the sibling. Every other consumer - the application
verification surface, the registry helpers, and roughly twenty test modules -
already reached the symbols through the package facade and needed no change. The
schema module keeps the predicate model in its own export list because
`ModeloRevision` genuinely declares a tuple of them, which is a real dependency
rather than a compatibility re-export; the two vocabulary constants were never in
that list and are not re-exported from it.

**Two prose sites would have misdirected a reader and were corrected with the
move.** The application-side predicate evaluator's docstring and the predicate
validator's own header comment both named the old module path as the canonical
home of the operator set. Left alone they would have sent a reader to a module
that no longer declares it - the same stale-prose defect this campaign has been
correcting elsewhere - so both were swept in the same commit.

Gate results after the change:

- Module size band: the schema module is absent from both the over-budget and
  the stale partitions. The stale partition is empty tree-wide. Two over-budget
  findings remain and are triaged below as peer-owned.
- Registry suite: 3164 passed.
- Predicate-vocabulary parity: the gate that binds the moved constant to the
  runtime evaluator's operator set passes, which is the check that the constant
  is still reachable through the facade and still in lock-step.
- Full-tree collect-only: 15062 collected, no collection errors, re-run
  immediately before the commit.
- Registry tree verification: verified true over 73 modelos, 90 revisions, 15774
  casillas, 1256 formulas and 568 legal references.
- Generated API reference: the drift check reports a conformant tree with no
  change due, because no module was added, moved or deleted - the sibling and
  its stub both already existed.
- Lint and format: clean across the registry package and every changed file.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
semantic index is broken and its service is stopped, with a standing instruction
not to start, restart, reindex or probe it. It was neither started nor probed.
Grounding was done with literal search plus whole-file reads. This waiver is
recorded because the mandate otherwise requires refusing the work outright.

Two gates are red for reasons outside this Step, both committed at the branch
head rather than uncommitted work. The module size gate reports the
configuration package entry point at 1252 lines and an AEAT auth module at 1268,
against the 1250 default. Neither is touched here and neither was absorbed:
editing another campaign's files to green a shared gate risks colliding with work
in flight, so they are reported as inventory for their owners. The lazy-import
policy gate is red on a peer's function-local import in the user-profile
validation module, with the ratchet, the ceiling-slack check and the baseline
reproduction all naming that one edge; nothing in the registry package appears in
any of its findings.

One test module produced a MemoryError under a scoped run and then passed 7 of 7
on an immediate clean re-run with no code change between the two. The machine was
carrying several concurrent full-suite runs at the time, so it is recorded as
resource exhaustion rather than a defect - but it is recorded, because an
unexplained error swallowed silently is how a real one hides.

A peer's uncommitted change in the classification-coherence module sits in the
same package and was NOT touched: its modification time predates every command
this Step ran by more than three hours, which is how the attribution was settled
rather than by assumption. It was excluded from the pathspec and left exactly as
found. A peer also had a separate campaign's work staged in the shared index at
commit time; the commit named its nine paths explicitly and the peer's staged
entries stayed in the index untouched. A peer held the index lock during both
staging and committing, which was waited out rather than cleared.

The mandatory code review has not been performed. No delegation tool was
available in this session, so the review is owed and should be dispatched by the
coordinator against commit `7007840311`.

The follow-up the previous extraction described is now closed, and its stated
sequencing held exactly: a Step owning both the module and its baseline entry
removed the entry and took the full concern in one commit, at which point the
module falls under the default with a wide margin and the sibling built there
absorbed the predicate model and its operator vocabulary.
